"""
Script to obtain user details from an LDAP server.
"""

from argparse import ArgumentParser, Namespace
from configparser import RawConfigParser
import json
import logging
from typing import Dict, List, TYPE_CHECKING
try:
    import ldap
    from ldap.ldapobject import LDAPObject
except ImportError:
    if not TYPE_CHECKING:
        ldap = None
        LDAPObject = object
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.log import Log_Setup

def parse_args(config: RawConfigParser) -> Namespace:
    """
    Parse command line arguments.
    """

    description = "Obtain repository versions and output JSON"
    parser = ArgumentParser(description=description)
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

def get_groups(client: LDAPObject, args: Namespace) -> List[str]:
    """
    Retrieve a list of group names from LDAP.
    """

    groups = client.search_s(args.root, ldap.SCOPE_SUBTREE,
                             'objectClass=posixgroup', ['cn'])
    return [group['cn'][0].decode('utf-8') for _, group in groups]

def get_members(client: LDAPObject, name: str, args: Namespace) \
        -> List[Dict[str, str]]:
    """
    Retrieve group members and their properties.

    Returns a list of dictionaries containing developer name, display name and
    email.
    """

    data: List[Dict[str, str]] = []
    group = client.search_s(args.root, ldap.SCOPE_SUBTREE,
                            f'cn={name}', [str(args.group_attr)])[0][1]
    if args.group_attr not in group:
        logging.warning('Group %s contains no members', name)
        return data

    query = '(|{})'.format(''.join([
        '({})'.format(args.search_filter.format(uid.decode('utf-8')))
        for uid in group[args.group_attr]
    ]))

    users = client.search_s(args.root, ldap.SCOPE_SUBTREE, query, [
        str(args.user_id), str(args.display_name), str(args.user_email)
    ])

    for _, user in users:
        if args.user_email not in user:
            logging.info('Skipped user without email %s', user[args.user_id][0])
            continue

        data.append({
            "name": user[args.user_id][0].decode('utf-8'),
            "display_name": user[args.display_name][0].decode('utf-8'),
            "email": user[args.user_email][0].decode('utf-8')
        })

    return data

def main() -> None:
    """
    Main entry point.
    """

    config = Configuration.get_settings()
    args = parse_args(config)

    if ldap is None:
        logging.critical('Cannot import module "ldap"')
        return

    client = ldap.initialize(args.server)
    client.set_option(ldap.OPT_REFERRALS, 0)
    client.simple_bind(args.manager, args.manager_password)

    project = Project(args.project)
    if args.group is not None:
        group = str(args.group)
    elif config.has_option('groups', project.key):
        group = config.get('groups', project.key)
    else:
        logging.critical('No group specified for project %s', project.key)
        logging.info('Known LDAP groups: %s',
                     ', '.join(get_groups(client, args)))
        return

    data = get_members(client, group, args)

    output_path = project.export_key / 'data_ldap.json'
    with output_path.open('w') as output_file:
        json.dump(data, output_file)

if __name__ == '__main__':
    main()
