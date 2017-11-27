"""
Generate a private and public key and distribute it to the correct locations.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
import logging
import os
import shutil
import subprocess
import sys
import tempfile
try:
    import urllib.parse
except ImportError:
    raise
import inform
try:
    from mock import MagicMock
    sys.modules['abraxas'] = MagicMock()
    from sshdeploy.key import Key
except ImportError:
    raise

from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.domain.source import Source, GitLab, GitHub, TFS
from gatherer.log import Log_Setup

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    parser = argparse.ArgumentParser(description='Generate and distribute new public keys')
    parser.add_argument('project', help='project key to generate keys for')
    parser.add_argument('--path', default='~/.ssh/id_rsa',
                        help='local path to store the main private key at')
    parser.add_argument('--ssh', default=config.get('ssh', 'host'),
                        help='Controller API host to distribute main key to')
    parser.add_argument('--no-ssh', action='store_false', dest='ssh',
                        help='Do not distribute key to controller API host')
    parser.add_argument('--cert', default=config.get('ssh', 'cert'),
                        help='HTTPS certificate of controller API host')
    parser.add_argument('--credentials', action='store_true', default=False,
                        help='Distribute keys to credential domains')
    parser.add_argument('--source', action='store_true', default=False,
                        help='Distribute keys to collected project sources')
    parser.add_argument('--gitlab', nargs='*',
                        help='GitLab host(s) to distribute keys to')
    parser.add_argument('--no-gitlab', dest='gitlab', action='store_false',
                        help='Do not distribute keys to collected GitLab hosts')
    parser.add_argument('--known-hosts', dest='known_hosts',
                        default='~/.ssh/known_hosts',
                        help='local path to store scanned SSH host keys in')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true',
                        default=False, help='Only show what would happen')

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

class Identity(object):
    """
    Object indicating a key pair for one or more certain sources that require
    credentials to function.
    """

    def __init__(self, project, key_path, known_hosts, dry_run=False):
        self.project = project
        self.key_path = key_path
        self.known_hosts = known_hosts
        self.dry_run = dry_run

        self._public_key = None
        self._environments = set()

    @property
    def public_key(self):
        """
        Retrieve the public key part of the credentials for the purpose of
        publishing it to different sources.

        Newlines at the end of the public key are removed. If the key did not
        yet exist, then it is generated.
        """

        if self._public_key is None:
            self._store_key()
            self._public_key = self._read_key()

        return self._public_key

    def _generate_key_pair(self):
        """
        Generate a public and private key pair for the project to be used as
        credentials for the sources.

        This returns a temporary filename path holding the key.
        """

        if self.dry_run:
            return None

        data = {
            'purpose': 'agent for the {} project'.format(self.project.key),
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

    def _store_key(self):
        """
        Check whether the public and private key pair already exists, and if not
        generate the key and store it at the key path location.
        """

        if not os.path.exists(self.key_path):
            logging.info('Generating new key pair to %s', self.key_path)
            if not self.dry_run:
                temp_key_name = self._generate_key_pair()
                shutil.move(temp_key_name, self.key_path)
                shutil.move('{}.pub'.format(temp_key_name),
                            '{}.pub'.format(self.key_path))
                os.chmod(self.key_path, 0o600)
        else:
            logging.info('Using existing key pair from %s', self.key_path)

    def _read_key(self):
        public_key_path = '{}.pub'.format(self.key_path) 
        if not os.path.exists(public_key_path):
            return False

        with open(public_key_path, 'r') as public_key_file:
            return public_key_file.read().rstrip('\n')

    def _scan_host(self, url):
        hostname = urllib.parse.urlsplit(url).hostname
        try:
            if os.path.exists(self.known_hosts):
                subprocess.check_call([
                    'ssh-keygen', '-R', hostname, '-f', self.known_hosts
                ])

            with open(os.devnull, 'w') as null_file:
                lines = subprocess.check_output(['ssh-keyscan', hostname],
                                                stderr=null_file)
            with open(self.known_hosts, 'ab') as known_hosts_file:
                known_hosts_file.write(lines)
        except subprocess.CalledProcessError:
            logging.exception('Could not scan host %s', hostname)

    def update_source(self, source):
        """
        Register the SSH public key for this identity to the source, if this is
        possible and necessary for this source, environment, and source type.
        """

        if self.public_key is False:
            logging.warning('No public key part for key %s to upload to %s',
                            self.key_path, source.url)
            return

        if source.environment is not None:
            if source.environment in self._environments:
                logging.info('SSH key for environment %r already added',
                             source.environment)
                return

            self._environments.add(source.environment)

        try:
            source.update_identity(self.project, self.public_key,
                                   dry_run=self.dry_run)
        except RuntimeError:
            logging.exception('Could not publish public key to %s source %s',
                              source.type, source.url)
            return

        self._scan_host(source.url)

def add_ssh_key(project, identities, source, known_hosts, dry_run=False):
    """
    Update the SSH key at the given source based on its credentials path.
    """

    if source is None:
        return

    key_path = source.credentials_path
    if key_path is None:
        logging.info('Source %s has no SSH key credentials', source.url)
        return

    if key_path not in identities:
        identities[key_path] = Identity(project, key_path, known_hosts,
                                        dry_run=dry_run)

    identities[key_path].update_source(source)

def make_source(domain):
    """
    Build a dummy source object based on a credentials domain.
    """

    if GitLab.is_gitlab_host(domain):
        return Source.from_type('gitlab', url='http://{}/'.format(domain),
                                name='dummy')
    if GitHub.is_github_host(domain):
        return Source.from_type('github', url='https://{}/'.format(domain),
                                name='dummy')
    if TFS.is_tfs_host(domain):
        return Source.from_type('tfs', url='http://{}/tfs'.format(domain),
                                name='dummy')

    return None

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)

    inform.Inform(mute=True)
    if args.dry_run:
        logging.info('Dry run: Logging output only describes what would happen')

    main_key = os.path.expanduser(args.path)
    known_hosts = os.path.expanduser(args.known_hosts)
    identities = {}

    if Configuration.has_value(args.ssh):
        identity = Identity(project, main_key, known_hosts,
                            dry_run=args.dry_run)
        source = Source.from_type('controller',
                                  url='https://{}/auth/'.format(args.ssh),
                                  name='Controller',
                                  certificate=args.cert)
        identity.update_source(source)

        identities[main_key] = identity

    if args.credentials:
        credentials = Configuration.get_credentials()
        for domain in credentials.sections():
            source = make_source(domain)
            if source:
                add_ssh_key(project, identities, source, known_hosts,
                            dry_run=args.dry_run)

    if args.gitlab is not False:
        # If --gitlab is not provided or it has no remaining arguments, then
        # fall back to a project source and the project definitions source.
        if not args.gitlab or (args.source and project.gitlab_source is not None):
            add_ssh_key(project, identities, project.gitlab_source, known_hosts,
                        dry_run=args.dry_run)
            add_ssh_key(project, identities, project.project_definitions_source,
                        known_hosts, dry_run=args.dry_run)
        else:
            for gitlab_host in args.gitlab:
                url = 'http://{}'.format(gitlab_host)
                source = Source.from_type('gitlab', url=url, name='GitLab')
                add_ssh_key(project, identities, source, known_hosts,
                            dry_run=args.dry_run)

if __name__ == "__main__":
    main()
