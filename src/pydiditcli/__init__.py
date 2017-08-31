import ConfigParser
from cStringIO import StringIO
import os
from optparse import OptionParser
import simplejson as json
import sys

parser = OptionParser()

parser.add_option('--user', action='store', nargs=1, type='string',
                  dest='username')
parser.add_option('--workspace-name', action='store', nargs=1, type='string',
                  dest='workspace_name')

parser.add_option('-t', '--todo', const='Todo', action='append_const',
                  dest='objects')
parser.add_option('-g', '--tag', const='Tag', action='append_const',
                  dest='objects')
parser.add_option('-p', '--project', const='Project', action='append_const',
                  dest='objects')
parser.add_option('-n', '--note', const='Note', action='append_const',
                  dest='objects')
parser.add_option('-w', '--workspace', const='Workspace', action='append_const',
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
parser.add_option('-m', '--move', action='append_const', const='move',
                  dest='operations')
parser.add_option('-l', '--link', action='append_const', const='link',
                  dest='operations')
parser.add_option('--unlink', action='store_true', dest='unlink',
                  default=False)
parser.add_option('-?', '--search', action='append_const', const='search',
                  dest='operations')

parser.add_option('-q', '--prereq', action='store_const', dest='relationship',
                  const='prereq', default='contain')
parser.add_option('-d', '--dependent', action='store_const', dest='relationship',
                  const='dependent', default='contain')
parser.add_option('-c', '--contains', action='store_const', dest='relationship',
                  const='contain', default='contain')
parser.add_option('-b', '--contained_by', action='store_const', dest='relationship',
                  const='contained_by', default='contain')

parser.add_option('-1', '--top', action='store_true', dest='top',
                  default=False)
parser.add_option('--bottom', action='store_true', dest='bottom',
                  default=False)

parser.add_option('--head', action='store_true', dest='head',
                  default=False)
parser.add_option('--all', action='store_true', dest='all',
                  default=False)
parser.add_option('-v', '--verbose', action='store_true', dest='verbose',
                  default=False)

parser.add_option('--add-user', action='store', nargs=1, type='string',
                  dest='add_user')
parser.add_option('--add-workspace-permission', action='store', nargs=2,
                  type='string', dest='add_workspace_permission')
parser.add_option('--revoke-workspace-permission', action='store', nargs=2,
                  type='string', dest='revoke_workspace_permission')

parser.add_option('--trade-initial-token', action='store', nargs=1,
                  type='string', dest='initial_token')


ini = ConfigParser.SafeConfigParser()
ini.read((os.path.expanduser('~/.pydidit-clirc'),))

backend_settings = dict(ini.items('backend'))
if 'remote' in backend_settings and backend_settings['remote']:
    import pydiditbackendweb as b
else:
    import pydiditbackend as b


links_to_language = {
    'contains_projects': 'contains',
    'contains_todos': 'contains',
    'contained_by_projects': 'is contained by',
    'prereq_todos': 'has prerequisite todos',
    'prereq_projects': 'has prerequisite projects',
    'dependent_todos': 'has dependent todos',
    'dependent_projects': 'has dependent projects',
    'tags': 'has tags',
    'projects': 'has projects',
    'todos': 'has todos',
    'notes': 'has notes',
}

def get_username(options, cli_settings):
    username = \
        cli_settings['username'] if 'username' in cli_settings else None
    if hasattr(options, 'username') and options.username is not None:
        username = options.username
    return username

def main():
    options, args = parser.parse_args()

    b.initialize(backend_settings)

    cli_settings = dict(ini.items('cli'))

    username = get_username(options, cli_settings)

    if 'remote' in backend_settings and backend_settings['remote']:
        if hasattr(options, 'initial_token') and \
           options.initial_token is not None:
            try:
                b.trade_initial_token(username, options.initial_token)
            except b.RemoteException as e:
                if e.code == 403:
                    print 'Your initial token was not accepted.  Please ' \
                          'check with your pydidit administrator.'
                    sys.exit(1)
                else:
                    raise e
            print 'Successfully authenticated!'
            return
        else:
            if not b.check_access_token(username):
                print 'Please use the --trade-initial-token option to authenticate.'
                sys.exit(1)

    if options.objects is None or len(options.objects) == 0:
        if options.operations is None or 'search' not in options.operations:
            options.objects = ['Todo']

    # Check for add user request
    if hasattr(options, 'add_user') and options.add_user is not None:
        b.create_user(unicode(options.add_user))
        b.commit()
        return

    if username is None:
        print 'No username defined'
        return

    users = b.get_users(unicode(username))
    if len(users) == 0:
        print 'User {0} not found.'.format(username)
        return
    if len(users) > 1:
        print 'Multiple users with username {0} found - this is unsupported.'\
            .format(username)
        return
    options.user_id = users[0]['user_id']

    workspace_name = cli_settings['workspace'] \
                     if 'workspace' in cli_settings \
                     else None
    if hasattr(options, 'workspace_name') and options.workspace_name is not None:
        workspace_name = options.workspace_name

    # If we just want to operate on workspaces, ignore the configured
    # workspace
    if len(options.objects) != 1 or options.objects[0] != 'Workspace':
        workspaces = b.get_workspaces(options.user_id, unicode(workspace_name))
        if len(workspaces) == 0:
            print 'Workspace {0} not found.'.format(workspace_name)
            return
        if len(workspaces) > 1:
            print 'Multiple workspaces with name {0} found - this is ' \
                  'unsupported.'.format(workspace_name)
            return
        options.workspace_id = workspaces[0]['id']

        # Next, check for add workspace permission or revoke workspace permission
        # request
        handled_workspace_permission = False
        for workspace_permission in (
            'add_workspace_permission',
            'revoke_workspace_permission'
        ):
            if getattr(options, workspace_permission, None) is not None:
                globals()[workspace_permission](options)
                handled_workspace_permission = True

        # Don't keep going if we did workspace permission work
        if handled_workspace_permission:
            return

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
            b.move(options.user_id, options.workspace_id, int(args[0]),
                direction='float', model_name=options.objects[0], all_the_way=options.top)
            b.commit()
        elif options.operations[0] == 'sink':
            b.move(options.user_id, options.workspace_id, int(args[0]),
                direction='sink', model_name=options.objects[0], all_the_way=options.bottom)
            b.commit()
        elif options.operations[0] == 'move':
            b.move(options.user_id, options.workspace_id, int(args[0]),
                int(args[1]), model_name=options.objects[0])
            b.commit()
        elif options.operations[0] == 'link':
            lnk(options, args)
        elif options.operations[0] == 'unlink':
            lnk(options, args)
        elif options.operations[0] == 'search':
            search(options, args)

def read(options, args):
    objs = None
    filter_by = {'id': args[0]} if not options.head and args is not None and len(args) == 1 else None

    objs = None
    if len(options.objects) == 1 and options.objects[0] == 'Workspace':
        objs = b.get_workspaces(options.user_id)
    else:
        objs = b.get(options.user_id, options.workspace_id, options.objects[0], options.all, filter_by)
    if options.head:
        objs = objs[:int(args[0])]
    if len(options.objects) == 1:
        print '{0}s:'.format(options.objects[0]), format(objs, options)
    else:
        for obj in objs:
            print '{0}:'.format(options.objects[0]), format(obj, options)
            related_attribute_name = b.relationship_name(obj['type'], options.objects[1], options.relationship)
            print '{0}'.format(links_to_language[related_attribute_name])
            related_objs = obj[related_attribute_name]
            print '\t{0}s:'.format(options.objects[1])
            for related_obj in related_objs:
                if not 'state' in related_obj or options.all or related_obj['state'] != 'completed':
                    print '\t', format(related_obj, options)


def add(options, args):
    if len(options.objects) == 1:
        if options.objects[0] == 'Workspace':
            # We are handling Workspace descriptions
            new_workspaces = b.create_workspace(options.user_id, [unicode(arg) for arg in args], [u'' for arg in args])
        else:
            created = b.put(options.user_id, options.workspace_id, options.objects[0], [unicode(arg) for arg in args])
            if len(created) == 0:
                raise Exception('Write forbidden.')
            if isinstance(created, dict):
                created = [created]
            if options.top and 'display_position' in created[0]:
                for obj in created:
                    b.move(options.user_id, options.workspace_id, obj, direction='float', all_the_way=True)
            print 'Created:', format(created, options)
        b.commit()
    else:
        raise Exception('One and only one object in add')


def update(options, args):
    if len(options.objects) == 1:
        if len(args) == 2:
            to_update = b.get(
                options.user_id,
                options.workspace_id,
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
                b.set_attributes(options.user_id, options.workspace_id, to_update, {
                    to_update['primary_descriptor']: value
                })
            else:
                for prop, value in (json.loads(args[1])).iteritems():
                    if isinstance(value, str):
                        value = unicode(value)
                    b.set_attributes(options.user_id, options.workspace_id,
                        to_update, {prop: value})
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
                options.user_id, options.workspace_id, options.objects[0],
                filter_by={'id': int(args[0])}
            )
            if len(to_delete) > 0:
                deleted = b.delete_from_db(options.user_id, options.workspace_id, to_delete[0])
                print 'Deleted:', format(deleted, options)
                b.commit()
            else:
                raise Exception('Todo with id {0} not found.'.format(
                    args[0]
                ))
        else:
            raise Exception('One and only one argument in delete')
    else:
        raise Exception('One and only one object in delete')


def complete(options, args):
    if len(options.objects) == 1:
        if len(args) == 1:
            to_complete = b.get(
                options.user_id, options.workspace_id, options.objects[0],
                filter_by={'id': int(args[0])}
            )[0]
            result = b.set_completed(options.user_id, options.workspace_id, to_complete)
            if result is not None:
                print 'Completed:', format(to_complete, options)
                b.commit()
        else:
            raise Exception('One and only one argument in complete')
    else:
        raise Exception('One and only one object in complete')


def search(options, args):
    if len(args) == 1:
        only = None
        if options.objects is not None:
            only = options.objects
        result = b.search(options.user_id, options.workspace_id, args[0], only=only)
        for obj_name, data in result.iteritems():
            print '{0}s:'.format(obj_name), format(data, options)
    else:
        raise Exception('One and only one argument in search')


def lnk(options, args):
    if len(options.objects) == 2:
        if len(args) == 2:
            obj = b.get(options.user_id, options.workspace_id,
                options.objects[0], filter_by={'id': int(args[0])})[0]
            related_obj = b.get(
                options.user_id, options.workspace_id,
                options.objects[1], filter_by={'id': int(args[1])}
            )[0]
            if options.unlink:
                b.unlink(options.user_id, options.workspace_id, obj,
                    related_obj, options.relationship)
            else:
                b.link(options.user_id, options.workspace_id, obj,
                    related_obj, options.relationship)
            b.commit()
        else:
            raise Exception('Two and only two arguments in link')
    else:
        raise Exception('Two and only two objects in link')


def add_workspace_permission(options):
    change_workspace_permission(
        options,
        options.add_workspace_permission[0],
        options.add_workspace_permission[1].split(','),
        b.give_permission
     )

def revoke_workspace_permission(options):
    change_workspace_permission(
        options,
        options.revoke_workspace_permission[0],
        options.revoke_workspace_permission[1].split(','),
        b.revoke_permission
     )

def change_workspace_permission(options, target_user_info, permissions,
                                backend_function):
    if isinstance(target_user_info, basestring):
        target_users = b.get_users(unicode(target_user_info))
        if len(target_users) == 0:
            print 'Target user {0} not found.'.format(target_user_info)
            return
        if len(target_users) > 1:
            print 'Multiple target users with username {0} found - ' \
                  'this is unsupported.'.format(target_user_info)
            return
        target_user_info = target_users[0]['user_id']
    print backend_function(
        options.user_id,
        options.workspace_id,
        target_user_info,
        permissions
    )
    b.commit()


def format(thing, options):
    if thing is None:
        return ''
    elif hasattr(thing, 'keys'):  # I'm a dict
        info = []
        if 'description' in thing:
            info.append(thing['description'])
        elif 'text' in thing:
            info.append(thing['text'])
        elif 'name' in thing:
            info.append(thing['name'])
        if options.verbose is True:
            if 'workspaces' in thing:
                workspace_names = []
                for workspace in thing['workspaces']:
                    workspace_names.append(workspace['name'])
                info.append(' '.join(workspace_names))
            if 'display_position' in thing:
                info.append(str(thing['display_position']))
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
    elif (hasattr(thing, '__iter__') or hasattr(thing, '__getitem__')) and not isinstance(thing, basestring): # I'm a list
        return '\n'.join(
            ['\t* {0}'.format(
                format(element, options)
            ) for element in thing]
        )
    else:
        return thing

