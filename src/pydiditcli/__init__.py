import ConfigParser
from cStringIO import StringIO
import os
from optparse import OptionParser
import simplejson as json

from pydiditbackend import initialize
from pydiditbackend import get
from pydiditbackend import put
from pydiditbackend import delete_from_db
from pydiditbackend import commit
from pydiditbackend import flush

parser = OptionParser()

parser.add_option('-t', '--todo', const='Todo', action='append_const',
                  dest='objects')
parser.add_option('-g', '--tag', const='Tag', action='append_const',
                  dest='objects')
parser.add_option('-p', '--project', const='Project', action='append_const',
                  dest='objects')
parser.add_option('-n', '--note', const='Note', action='append_const',
                  dest='objects')

parser.add_option('-c', '--create', action='append_const', const='create',
                  dest='operations')
parser.add_option('-d', '--delete', action='append_const', const='delete',
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

parser.add_option('-a', '--all', action='store_true', dest='all',
                  default=False)
parser.add_option('-v', '--verbose', action='store_true', dest='verbose',
                  default=False)


def main():
    ini = ConfigParser.SafeConfigParser()
    ini.read((os.path.expanduser('~/.pydiditrc'),
              os.path.expanduser('~/.pydidit-clirc'),))

    options, args = parser.parse_args()

    config = StringIO()
    ini.write(config)
    config.seek(0)
    initialize(external_config_fp=config)

    if options.operations is None:
        read(options)
    elif len(options.operations) > 1:
        raise Exception('Only one operation at a time supported.')
    else:
        if options.operations[0] == 'read':
            read(options)
        elif options.operations[0] == 'create':
            create(options, args)
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
            link(options, args)


def read(options):
    if len(options.objects) > 0:
        objs = get(options.objects[0], options.all)
        if len(options.objects) == 1:
            print '{0}s:'.format(options.objects[0]), format(objs, options)
        else:
            for obj in objs:
                print '{0}:'.format(options.objects[0]), format(obj, options)
                related_objs = getattr(
                    obj,
                    '{0}s'.format(options.objects[1].lower())
                )
                print '\t{0}s:'.format(options.objects[1])
                for related_obj in related_objs:
                    print '\t', format(related_obj, options)


def create(options, args):
    if len(options.objects) == 1:
        created = put(options.objects[0], args[0])
        flush()
        print 'Created:', format(created, options)
        commit()
    else:
        raise Exception('One and only one object in create')


def update(options, args):
    if len(options.objects) == 1:
        if len(args) == 2:
            to_update = get(
                options.objects[0],
                filter_by={'id': int(args[0])}
            )[0]
            for prop, value in (json.loads(args[1])).iteritems():
                if isinstance(value, str):
                    value = unicode(value)
                setattr(to_update, prop, value)
            print 'Updated:', format(to_update, options)
            commit()
        else:
            raise Exception('Two and only two arguments in update')
    else:
        raise Exception('One and only one object in update')


def delete(options, args):
    if len(options.objects) == 1:
        if len(args) == 1:
            to_delete = get(
                options.objects[0],
                filter_by={'id': int(args[0])}
            )[0]
            delete_from_db(to_delete)
            print 'Deleted:', format(to_delete, options)
            commit()
        else:
            raise Exception('One and only one argument in delete')
    else:
        raise Exception('One and only one object in delete')


def complete(options, args):
    if len(options.objects) == 1:
        if len(args) == 1:
            to_complete = get(
                options.objects[0],
                filter_by={'id': int(args[0])}
            )[0]
            if hasattr(to_complete, 'set_completed'):
                to_complete.set_completed()
                print 'Completed:', format(to_complete, options)
                commit()
            else:
                raise Exception(
                    'Object {0} cannot be set as complete'.format(
                        options.objects[0]
                    )
                )
        else:
            raise Exception('One and only one argument in complete')
    else:
        raise Exception('One and only one object in complete')


def flt(options, args):
    if len(options.objects) == 1:
        if len(args) == 1:
            objs = get(options.objects[0])
            for obj in objs:
                if obj.id == int(args[0]):
                    idx = objs.index(obj)
                    if idx != 0:
                        temp = objs[idx - 1].display_position
                        objs[idx - 1].display_position = obj.display_position
                        obj.display_position = temp
            commit()
        else:
            raise Exception('One and only one arguments in float')
    else:
        raise Exception('One and only one object in float')


def sink(options, args):
    if len(options.objects) == 1:
        if len(args) == 1:
            objs = get(options.objects[0])
            for obj in objs:
                if obj.id == int(args[0]):
                    idx = objs.index(obj)
                    if idx != len(objs) - 1:
                        temp = objs[idx + 1].display_position
                        objs[idx + 1].display_position = obj.display_position
                        obj.display_position = temp
            commit()
        else:
            raise Exception('One and only one arguments in sink')
    else:
        raise Exception('One and only one object in sink')


def link(options, args):
    if len(options.objects) == 2:
        if len(args) == 2:
            obj = get(options.objects[0], filter_by={'id': int(args[0])})[0]
            related_obj = get(
                options.objects[1],
                filter_by={'id': int(args[1])}
            )[0]
            getattr(obj, '{0}s'.format(
                options.objects[1].lower()
            )).append(related_obj)
            commit()
        else:
            raise Exception('Two and only two arguments in link')
    else:
        raise Exception('Two and only two objects in link')


def format(thing, options):
    if thing is None:
        return ''
    if hasattr(thing, '__iter__'):
        return '\n'.join(
            ['\t* {0}'.format(
                format(element, options)
            ) for element in thing]
        )
    else:
        info = []
        if hasattr(thing, 'description'):
            info.append(thing.description)
        elif hasattr(thing, 'text'):
            info.append(thing.text)
        elif hasattr(thing, 'name'):
            info.append(thing.name)
        if options.verbose is True:
            if hasattr(thing, 'display_position'):
                info.append(thing.display_position)
            if hasattr(thing, 'created_at'):
                info.append(thing.created_at.strftime('%Y-%m-%d %H:%M'))
            if hasattr(thing, 'modified_at'):
                info.append(thing.modified_at.strftime('%Y-%m-%d %H:%M'))
        return '{0} id {1}{2}: {3}'.format(
            thing.__class__.__name__,
            thing.id,
            ' ({0})'.format(thing.state) if hasattr(thing, 'state') else '',
            '  '.join(info),
        )
