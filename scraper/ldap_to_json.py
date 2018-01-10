"""
Script to obtain user details from an LDAP server.
"""

import argparse
import json
import logging
import os.path
import ldap
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup

def parse_args(config):
    """
    Parse command line arguments.
    """

    description = "Obtain repository versions and output JSON"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="Project key")
    parser.add_argument("--group", default=None, help="Group name")
    parser.add_argument("--server", default=config.get('ldap', 'server'),
                        help="URI for the LDAP server")
    parser.add_argument("--root", default=config.get('ldap', 'root_dn'),
                        help="Root DN")
    parser.add_argument("--manager", default=config.get('ldap', 'manager_dn'),
                        help="Manager DN")
    parser.add_argument("--manager-password", dest='manager_password',
                        default=config.get('ldap', 'manager_password'),
                        help="Manager password")
    parser.add_argument("--group-attr", dest='group_attr',
                        default=config.get('ldap', 'group_attr'),
                        help="Group membership attribute")
    parser.add_argument("--search-filter", dest='search_filter',
                        default=config.get('ldap', 'search_filter'),
                        help="Member user search query template")
    parser.add_argument("--display-name", dest='display_name',
                        default=config.get('ldap', 'display_name'),
                        help="Display name attribute")
    parser.add_argument("--user-id", dest='user_id', default='uid',
                        help="User ID attribute")
    parser.add_argument("--user-email", dest='user_email', default='mail',
                        help="User email attribute")

    Log_Setup.add_argument(parser)
    Log_Setup.add_upload_arguments(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def get_members(client, name, args):
    """
    Retrieve group members and their properties.

    Returns a list of dictionaries containing developer name, display name and
    email.
    """

    data = []
    group = client.search_s(args.root, ldap.SCOPE_SUBTREE,
                            'cn={}'.format(name), [str(args.group_attr)])[0][1]
    if args.group_attr not in group:
        logging.warning('Group %s contains no members', name)
        return data

    query = '(|{})'.format(''.join([
        '({})'.format(args.search_filter.format(uid)) for uid in group[args.group_attr]
    ]))

    users = client.search_s(args.root, ldap.SCOPE_SUBTREE, query, [
        str(args.user_id), str(args.display_name), str(args.user_email)
    ])

    for _, user in users:
        if args.user_email not in user:
            logging.info('Skipped user without email %s', user[args.user_id][0])
            continue

        data.append({
            "name": user[args.user_id][0],
            "display_name": user[args.display_name][0],
            "email": user[args.user_email][0]
        })

    return data

def main():
    """
    Main entry point.
    """

    config = Configuration.get_settings()
    args = parse_args(config)
    project = Project(args.project)
    if args.group is not None:
        group = args.group
    elif config.has_option('groups', project.key):
        group = config.get('groups', project.key)
    else:
        logging.critical('No group specified for project %s', project.key)
        return

    client = ldap.initialize(args.server)
    client.set_option(ldap.OPT_REFERRALS, 0)
    client.simple_bind(args.manager, args.manager_password)

    data = get_members(client, group, args)

    output_filename = os.path.join(project.export_key, 'data_ldap.json')
    with open(output_filename, 'w') as output_file:
        json.dump(data, output_file)

if __name__ == '__main__':
    main()
