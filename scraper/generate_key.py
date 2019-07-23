"""
Generate a private and public key and distribute it to the correct locations.
"""

from argparse import ArgumentParser, Namespace
import logging
from os import devnull
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, Hashable, List, MutableMapping, Optional, Set, Union
import urllib.parse
import inform
try:
    from unittest.mock import MagicMock
    sys.modules['abraxas'] = MagicMock()
    from sshdeploy.key import Key
except ImportError:
    sys.modules.pop('abraxas')
    raise

from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.domain.source import Source, GitLab, GitHub, TFS
from gatherer.log import Log_Setup

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    parser = ArgumentParser(description='Generate and distribute new public keys')
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

def get_temp_filename() -> str:
    """
    Retrieve a secure (not guessable) temporary file name.
    """

    with tempfile.NamedTemporaryFile() as tmpfile:
        filename = tmpfile.name

    return filename

class Identity:
    """
    Object indicating a key pair for one or more certain sources that require
    credentials to function.
    """

    def __init__(self, project: Project, key_path: Path, known_hosts: Path,
                 dry_run: bool = False) -> None:
        self.project = project
        self.key_path = key_path
        self.known_hosts = known_hosts
        self.dry_run = dry_run

        self._public_key: Optional[Union[str, bool]] = None
        self._environments: Set[Hashable] = set()

    @property
    def public_key(self) -> Union[str, bool]:
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

    def _generate_key_pair(self) -> Optional[str]:
        """
        Generate a public and private key pair for the project to be used as
        credentials for the sources.

        This returns a temporary filename path holding the key.
        """

        if self.dry_run:
            return None

        data: Dict[str, Union[str, bool, Dict[str, Union[str, List[str]]]]] = {
            'purpose': f'agent for the {self.project.key} project',
            'keygen-options': '',
            'abraxas-account': False,
            'servers': {},
            'clients': {}
        }
        update: List[str] = []
        key_file = get_temp_filename()
        key = Key(key_file, data, update, set(), False)
        key.generate()
        return key.keyname

    def _store_key(self) -> None:
        """
        Check whether the public and private key pair already exists, and if not
        generate the key and store it at the key path location.
        """

        if not self.key_path.exists():
            logging.info('Generating new key pair to %s', self.key_path)
            temp_key_name = self._generate_key_pair()
            if temp_key_name is not None:
                shutil.move(temp_key_name, str(self.key_path))
                shutil.move(f'{temp_key_name}.pub', f'{self.key_path}.pub')
                self.key_path.chmod(0o600)
        else:
            logging.info('Using existing key pair from %s', self.key_path)

    def _read_key(self) -> Union[str, bool]:
        public_key_path = Path(f'{self.key_path}.pub')
        if not public_key_path.exists():
            return False

        with public_key_path.open('r') as public_key_file:
            return public_key_file.read().rstrip('\n')

    def _scan_host(self, url: str) -> None:
        hostname = urllib.parse.urlsplit(url).hostname
        if hostname is None:
            logging.warning('Cannot extract hostname from source URL %s', url)
            return

        try:
            if self.known_hosts.exists():
                logging.info('Removing old host keys for %s from %s',
                             hostname, self.known_hosts)
                if not self.dry_run:
                    subprocess.check_call([
                        'ssh-keygen', '-R', hostname, '-f', self.known_hosts
                    ])

            logging.info('Scanning SSH host %s for keys and appending to %s',
                         hostname, self.known_hosts)
            if not self.dry_run:
                with open(devnull, 'w') as null_file:
                    lines = subprocess.check_output(['ssh-keyscan', hostname],
                                                    stderr=null_file)
                with self.known_hosts.open('ab') as known_hosts_file:
                    known_hosts_file.write(lines)
        except subprocess.CalledProcessError:
            logging.exception('Could not scan host %s', hostname)

    def update_source(self, source: Source) -> None:
        """
        Register the SSH public key for this identity to the source, if this is
        possible and necessary for this source, environment, and source type.
        """

        if source.environment is not None:
            if source.environment in self._environments:
                logging.info('SSH key for environment %r already checked',
                             source.environment)
                return

            self._environments.add(source.environment)

        if isinstance(self.public_key, str):
            try:
                source.update_identity(self.project, self.public_key,
                                       dry_run=self.dry_run)
            except RuntimeError:
                logging.exception('Cannot publish public key to %s source %s',
                                  source.type, source.plain_url)
                return
        else:
            # We only have a private key part, e.g., a deploy key.
            # Log this and still scan the source for host keys.
            logging.warning('No public key part for key %s to upload to %s',
                            self.key_path, source.plain_url)

        self._scan_host(source.plain_url)

def add_ssh_key(project: Project, identities: MutableMapping[Path, Identity],
                source: Optional[Source], known_hosts: Path,
                dry_run: bool = False) -> None:
    """
    Update the SSH key at the given source based on its credentials path.
    """

    if source is None:
        return

    if source.credentials_path is None:
        logging.info('Source %s has no SSH key credentials', source.plain_url)
        return

    key_path = Path(source.credentials_path)
    if key_path not in identities:
        identities[key_path] = Identity(project, key_path, known_hosts,
                                        dry_run=dry_run)

    identities[key_path].update_source(source)

def make_source(domain: str) -> Optional[Source]:
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

def add_gitlab_key(project: Project, identities: MutableMapping[Path, Identity],
                   known_hosts: Path, args: Namespace) -> None:
    """
    Add additional keys to GitLab hosts, such as project definitions sources
    and known project GitLab hosts.

    If --gitlab is not provided or it has no remaining arguments, then
    fall back to a project source and the project definitions source.
    """

    if not args.gitlab or (args.source and project.gitlab_source is not None):
        add_ssh_key(project, identities, project.gitlab_source, known_hosts,
                    dry_run=args.dry_run)
        add_ssh_key(project, identities, project.project_definitions_source,
                    known_hosts, dry_run=args.dry_run)
    else:
        for gitlab_host in args.gitlab:
            url = f'http://{gitlab_host}'
            source = Source.from_type('gitlab', url=url, name='GitLab')
            add_ssh_key(project, identities, source, known_hosts,
                        dry_run=args.dry_run)

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()
    project = Project(args.project)

    inform.Inform(mute=True)
    if args.dry_run:
        logging.info('Dry run: Logging output only describes what would happen')

    main_key = Path(args.path).expanduser()
    known_hosts = Path(args.known_hosts).expanduser()
    identities: Dict[Path, Identity] = {}

    if args.ssh and Configuration.has_value(args.ssh):
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
            add_ssh_key(project, identities, make_source(domain), known_hosts,
                        dry_run=args.dry_run)

    if args.gitlab is not False:
        add_gitlab_key(project, identities, known_hosts, args)

if __name__ == "__main__":
    main()
