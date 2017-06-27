"""
Generate a private and public key and distribute it to the correct locations.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
from configparser import RawConfigParser
import json
import logging
import os
import shutil
import sys
import tempfile
import gitlab3
import inform
import requests
try:
    from mock import MagicMock
    sys.modules['abraxas'] = MagicMock()
    from sshdeploy.key import Key
except ImportError:
    raise

from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.domain.source import GitLab
from gatherer.log import Log_Setup

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    parser = argparse.ArgumentParser(description='Generate and distribute new public key')
    parser.add_argument('project', help='project key to retrieve for')
    parser.add_argument('--path', default='~/.ssh/id_rsa',
                        help='local path to store the private key at')
    parser.add_argument('--ssh', default=config.get('ssh', 'host'),
                        help='Controller API host to distribute key to')
    parser.add_argument('--no-ssh', action='store_false', dest='ssh',
                        help='Do not distribute key to controller API host')
    parser.add_argument('--cert', default=config.get('ssh', 'cert'),
                        help='HTTPS certificate of controller API host')
    parser.add_argument('--gitlab', nargs='?', const=True,
                        help='GitLab host to distribute key to')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)

    return args

def get_temp_filename():
    """
    Retrieve a secure (not guessable) temporary file name.
    """

    with tempfile.NamedTemporaryFile() as tmpfile:
        filename = tmpfile.name

    return filename

def generate_key_pair(project):
    """
    Generate a public and private key pair for the project.
    """

    data = {
        'purpose': 'agent for the {} project'.format(project.key),
        'keygen-options': '',
        'abraxas-account': False,
        'servers': {},
        'clients': {}
    }
    update = []
    key_file = get_temp_filename()
    key = Key(key_file, data, update, {}, False)
    key.generate()
    return key.keyname

def export_secrets(secrets):
    """
    Write a configuration file with secrets according to a dictionary structure
    with a depth of two levels (section names, configuration keys and values).
    """

    parser = RawConfigParser()
    for section, section_secrets in secrets.items():
        parser.add_section(section)
        for key, value in section_secrets.items():
            parser.set(section, key, value)

    with open('secrets.cfg', 'w') as secrets_file:
        parser.write(secrets_file)

def update_controller_key(host, project, cert, public_key):
    """
    Update the public key in a controller API instance.
    """

    url = 'https://{}/auth/agent.py?project={}'.format(host, project.jira_key)
    request = requests.post(url, data={'public_key': public_key}, verify=cert)

    if request.status_code != requests.codes['ok']:
        raise RuntimeError('HTTP error {}: {}'.format(request.status_code, request.text))

    # In return for our public key, we may receive some secrets (salts).
    # Export these to a file since the data is never received again.
    try:
        response = json.loads(request.text)
    except ValueError:
        logging.exception('Invalid JSON response from controller API: %s',
                          request.text)
        return

    export_secrets(response)

def update_gitlab_key(source, public_key):
    """
    Update the public keys of a user in a GitLab instance.
    """

    if source is None:
        raise RuntimeError('No GitLab source could be created')

    if source.gitlab_token is None:
        raise RuntimeError('GitLab instance {} has no API token'.format(source.host))

    api = gitlab3.GitLab(source.host, source.gitlab_token)
    # pylint: disable=no-member
    user = api.current_user()

    logging.info('Deleting old SSH keys for the agent from GitLab...')
    title = 'GROS agent'
    for key in user.ssh_keys():
        if key.title == title:
            user.delete_ssh_key(key)

    logging.info('Adding new SSH key to GitLab')
    user.add_ssh_key(title, public_key)

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)

    inform.Inform(mute=True)

    private_key_filename = os.path.expanduser(args.path)
    if not os.path.exists(private_key_filename):
        key_filename = generate_key_pair(project)
        shutil.move(key_filename, private_key_filename)
        shutil.move('{}.pub'.format(key_filename),
                    '{}.pub'.format(private_key_filename))
        os.chmod(private_key_filename, 0o600)

    with open('{}.pub'.format(private_key_filename), 'r') as public_key_file:
        public_key = public_key_file.read()

    if args.ssh and Configuration.has_value(args.ssh):
        update_controller_key(args.ssh, project, args.cert, public_key)

    if args.gitlab:
        if args.gitlab is True:
            source = project.gitlab_source
        else:
            url = 'http://{}'.format(args.gitlab)
            source = GitLab(url=url, name='GitLab', source_type='gitlab')

        try:
            update_gitlab_key(source, public_key)
        except RuntimeError:
            logging.exception('Could not publish public key to GitLab')

if __name__ == "__main__":
    main()
