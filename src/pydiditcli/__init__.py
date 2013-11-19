import ConfigParser
from cStringIO import StringIO
import os
from optparse import OptionParser
import simplejson as json

parser = OptionParser()

parser.add_option('-t', '--todo', const='Todo', action='append_const',
                  dest='objects')
parser.add_option('-g', '--tag', const='Tag', action='append_const',
                  dest='objects')
parser.add_option('-p', '--project', const='Project', action='append_const',
                  dest='objects')
parser.add_option('-n', '--note', const='Note', action='append_const',
                  dest='objects')

parser.add_option('-a', '--add', action='append_const', const='add',
                  dest='operations')
parser.add_option('--delete', action='append_const', const='delete',
                  dest='operations')
parser.add_option('-u', '--update', action='append_const', const='update',
                  dest='operations')
parser.add_option('-r', '--read', action='append_const', const='read',
                  dest='operations')
parser.add_option('-x', '--complete', action='append_const', const='complete',
                  dest='operations')
parser.add_option('-f', '--float', action='append_const', const='float',
                  dest='operations')
parser.add_option('-s', '--sink', action='append_const', const='sink',
                  dest='operations')
parser.add_option('-l', '--link', action='append_const', const='link',
                  dest='operations')

parser.add_option('--unlink', action='store_true', dest='unlink',
                  default=False)

parser.add_option('-q', '--prereq', action='store_const', dest='relationship',
                  const='prereq', default='contain')
parser.add_option('-d', '--dependent', action='store_const', dest='relationship',
                  const='dependent', default='contain')
parser.add_option('-c', '--contains', action='store_const', dest='relationship',
                  const='contain', default='contain')
parser.add_option('-b', '--contained_by', action='store_const', dest='relationship',
                  const='contained_by', default='contain')

parser.add_option('--all', action='store_true', dest='all',
                  default=False)
parser.add_option('-v', '--verbose', action='store_true', dest='verbose',
                  default=False)


ini = ConfigParser.SafeConfigParser()
ini.read((os.path.expanduser('~/.pydiditrc'),
          os.path.expanduser('~/.pydidit-clirc'),))

backend_settings = dict(ini.items('backend'))
if 'remote' in backend_settings and backend_settings['remote']:
    import pydiditbackendweb as b
else:
    import pydiditbackend as b


links_to_language = {
    'contain': 'contains',
    'contained_by': 'is contained by',
}

def main():
    options, args = parser.parse_args()

    if options.objects is None or len(options.objects) == 0:
        options.objects = ['Todo']

    config = StringIO()
    ini.write(config)
    config.seek(0)
    b.initialize(external_config_fp=config)

    if options.operations is None:
        read(options, args)
    elif len(options.operations) > 1:
        raise Exception('Only one operation at a time supported.')
    else:
        if options.operations[0] == 'read':
            read(options, args)
        elif options.operations[0] == 'add':
            add(options, args)
        elif options.operations[0] == 'update':
            update(options, args)
        elif options.operations[0] == 'delete':
            delete(options, args)
        elif options.operations[0] == 'complete':
            complete(options, args)
        elif options.operations[0] == 'float':
            flt(options, args)
        elif options.operations[0] == 'sink':
            sink(options, args)
        elif options.operations[0] == 'link':
            lnk(options, args)
        elif options.operations[0] == 'unlink':
            lnk(options, args)

def read(options, args):
    objs = b.get(options.objects[0], options.all, filter_by=({'id': args[0]} if args is not None and len(args) == 1 else None))
    if len(options.objects) == 1:
        print '{0}s:'.format(options.objects[0]), format(objs, options)
    else:
        for obj in objs:
            print '{0}:'.format(options.objects[0]), format(obj, options)
            print '{0}'.format(links_to_language[options.relationship])
            related_attribute_name = b.relationship_name(obj['type'], options.objects[1], options.relationship)
            related_objs = obj[related_attribute_name]
            print '\t{0}s:'.format(options.objects[1])
            for related_obj in related_objs:
                if not 'state' in related_obj or options.all or related_obj['state'] != 'completed':
                    print '\t', format(related_obj, options)

def add(options, args):
    if len(options.objects) == 1:
        created = b.put(options.objects[0], unicode(args[0]))
        print 'Created:', format(created, options)
        b.commit()
    else:
        raise Exception('One and only one object in add')


def update(options, args):
    if len(options.objects) == 1:
        if len(args) == 2:
            to_update = b.get(
                options.objects[0],
                filter_by={'id': int(args[0])}
            )[0]
            update = None
            try:
                update = json.loads(args[1]) # FIXME: is there something in simplejson that lets me just check whether a string is valid JSON?
            except json.JSONDecodeError as e:
                value = args[1]
                if isinstance(value, str):
                    value = unicode(value)
                b.set_attributes(to_update, {
                    to_update['primary_descriptor']: value
                })
            else:
                for prop, value in (json.loads(args[1])).iteritems():
                    if isinstance(value, str):
                        value = unicode(value)
                    b.set_attributes(to_update, {prop: value})
            print 'Updated:', format(to_update, options)
            b.commit()
        else:
            raise Exception('Two and only two arguments in update')
    else:
        raise Exception('One and only one object in update')


def delete(options, args):
    if len(options.objects) == 1:
        if len(args) == 1:
            to_delete = b.get(
                options.objects[0],
                filter_by={'id': int(args[0])}
            )[0]
            b.delete_from_db(to_delete)
            print 'Deleted:', format(to_delete, options)
            b.commit()
        else:
            raise Exception('One and only one argument in delete')
    else:
        raise Exception('One and only one object in delete')


def complete(options, args):
    if len(options.objects) == 1:
        if len(args) == 1:
            to_complete = b.get(
                options.objects[0],
                filter_by={'id': int(args[0])}
            )[0]
            result = b.set_completed(to_complete)
            if result is not None:
                print 'Completed:', format(to_complete, options)
                b.commit()
        else:
            raise Exception('One and only one argument in complete')
    else:
        raise Exception('One and only one object in complete')


def flt(options, args):
    if len(options.objects) == 1:
        if len(args) == 1:
            objs = b.get(options.objects[0])
            for obj in objs:
                if obj['id'] == int(args[0]):
                    idx = objs.index(obj)
                    if idx != 0:
                        temp = objs[idx - 1]['display_position']
                        b.set_attributes(objs[idx - 1], {'display_position': obj['display_position']})
                        b.set_attributes(obj, {'display_position': temp})
            b.commit()
        else:
            raise Exception('One and only one arguments in float')
    else:
        raise Exception('One and only one object in float')


def sink(options, args):
    if len(options.objects) == 1:
        if len(args) == 1:
            objs = b.get(options.objects[0])
            for obj in objs:
                if obj['id'] == int(args[0]):
                    idx = objs.index(obj)
                    if idx != len(objs) - 1:
                        temp = objs[idx + 1]['display_position']
                        b.set_attributes(objs[idx + 1], {'display_position': obj['display_position']})
                        b.set_attributes(obj, {'display_position': temp})
            b.commit()
        else:
            raise Exception('One and only one arguments in sink')
    else:
        raise Exception('One and only one object in sink')


def lnk(options, args):
    if len(options.objects) == 2:
        if len(args) == 2:
            obj = b.get(options.objects[0], filter_by={'id': int(args[0])})[0]
            related_obj = b.get(
                options.objects[1],
                filter_by={'id': int(args[1])}
            )[0]
            if options.unlink:
                b.unlink(obj, related_obj, options.relationship)
            else:
                b.link(obj, related_obj, options.relationship)
            b.commit()
        else:
            raise Exception('Two and only two arguments in link')
    else:
        raise Exception('Two and only two objects in link')


def format(thing, options):
    if thing is None:
        return ''
    if hasattr(thing, '__iter__'):
        if hasattr(thing, 'keys'):  # I'm a dict
            info = []
            if 'description' in thing:
                info.append(thing['description'])
            elif 'text' in thing:
                info.append(thing['text'])
            elif 'name' in thing:
                info.append(thing['name'])
            if options.verbose is True:
                if 'display_position' in thing:
                    info.append(thing['display_position'])
                if 'created_at' in thing:
                    info.append(thing['created_at'].strftime('%Y-%m-%d %H:%M'))
                if 'modified_at' in thing:
                    info.append(thing['modified_at'].strftime('%Y-%m-%d %H:%M'))
            return '{0} id {1}{2}: {3}'.format(
                thing['type'],
                thing['id'],
                ' ({0})'.format(thing['state']) if 'state' in thing else '',
                '  '.join(info),
            )
        else:  # I'm a list
            return '\n'.join(
                ['\t* {0}'.format(
                    format(element, options)
                ) for element in thing]
            )

