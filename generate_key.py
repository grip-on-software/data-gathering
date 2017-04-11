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

from gatherer.domain.source import GitLab
from gatherer.log import Log_Setup

def parse_args():
    """
    Parse command line arguments.
    """

    config = RawConfigParser()
    config.read("settings.cfg")

    parser = argparse.ArgumentParser(description='Generate and distribute new public key')
    parser.add_argument('project', help='project key to retrieve for')
    parser.add_argument('--path', default='~/.ssh/id_rsa',
                        help='local path to store the private key at')
    parser.add_argument('--ssh', default=config.get('ssh', 'host'),
                        help='Controller API host to distribute key to')
    parser.add_argument('--cert', default=config.get('ssh', 'cert'),
                        help='HTTPS certificate of controller API host')
    parser.add_argument('--gitlab', help='GitLab host to distribute key to')

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

def generate_key_pair(project_key):
    """
    Generate a public and private key pair for the project.
    """

    data = {
        'purpose': 'agent for the {} project'.format(project_key),
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

def update_controller_key(host, project, cert, public_key):
    """
    Update the public key in a controller API instance.
    """

    url = 'https://{}/auth/agent.py?project={}'.format(host, project)
    request = requests.post(url, data={'public_key': public_key}, verify=cert)

    if request.status_code != requests.codes['ok']:
        raise RuntimeError('HTTP error {}: {}'.format(request.status_code, request.text))

def update_gitlab_key(source, public_key):
    """
    Update the public keys of a user in a GitLab instance.
    """

    if source.gitlab_token is None:
        raise RuntimeError('GitLab instance {} has no API token'.format(source.host))

    api = gitlab3.GitLab(source.host, source.gitlab_token)
    # pylint: disable=no-member
    user = api.current_user()

    logging.info('Deleting old SSH keys for the agent from GitLab...')
    title = 'GROS agent'
    for key in user.ssh_keys(title=title):
        user.delete_ssh_key(str(key.id))

    logging.info('Adding new SSH key to GitLab')
    user.add_ssh_key(title, public_key)

def main():
    """
    Main entry point.
    """

    args = parse_args()
    inform.Inform(mute=True)

    private_key_filename = os.path.expanduser(args.path)
    if not os.path.exists(private_key_filename):
        key_filename = generate_key_pair(args.project)
        shutil.move(key_filename, private_key_filename)
        shutil.move('{}.pub'.format(key_filename),
                    '{}.pub'.format(private_key_filename))
        os.chmod(private_key_filename, 0600)

    with open('{}.pub'.format(private_key_filename), 'r') as public_key_file:
        public_key = public_key_file.read()

    if args.ssh:
        update_controller_key(args.ssh, args.project, args.cert, public_key)

    if args.gitlab:
        url = 'http://{}'.format(args.gitlab)
        source = GitLab(url=url, name='GitLab', source_type='gitlab')
        update_gitlab_key(source, public_key)

if __name__ == "__main__":
    main()
