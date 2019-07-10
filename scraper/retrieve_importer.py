"""
Script for downloading the Java database importer from a URL and extracting it
such that the Jenkins scraper can run all programs.
"""

from argparse import ArgumentParser, Namespace
import filecmp
import logging
from pathlib import Path
import shutil
import tempfile
from typing import Optional, Union
from zipfile import ZipFile
# Not-standard imports
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
from gatherer.config import Configuration
from gatherer.files import File_Store
from gatherer.jenkins import Jenkins
from gatherer.log import Log_Setup
from gatherer.request import Session

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    verify_config = config.get('jenkins', 'verify')
    verify: Union[str, bool] = verify_config
    if not Configuration.has_value(verify_config):
        verify = False
    elif not Path(verify_config).exists():
        verify = True

    username: Optional[str] = config.get('jenkins', 'username')
    password: Optional[str] = config.get('jenkins', 'password')
    if not Configuration.has_value(username):
        username = None
        password = None

    description = 'Retrieve the database importer and auxiliary data'
    parser = ArgumentParser(description=description)
    parser.add_argument('--base', default='.',
                        help='directory to place the importer and libraries in')
    parser.add_argument('--force', action='store_true', default=False,
                        help='override existing data files even if they differ')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--path', default=None,
                       help='local path to retrieve the dist directory from')
    group.add_argument('--jenkins', nargs='?', default=None,
                       const=config.get('jenkins', 'host'),
                       help='Base URL of a Jenkins instance to retrieve from')
    group.add_argument('--url', default=config.get('importer', 'url'),
                       help='url to retrieve a dist.zip file from')

    store = parser.add_argument_group('Data store', 'Dropins data store')
    store.add_argument('--type', default=config.get('dropins', 'type'),
                       help='type of the data store (owncloud)')
    store.add_argument('--store', default=config.get('dropins', 'url'),
                       help='URL of the data store')
    store.add_argument('--username', default=config.get('dropins', 'username'),
                       help='user to connect to the file store with')
    store.add_argument('--password', default=config.get('dropins', 'password'),
                       help='password to connect to the file store with')
    store.add_argument('--no-files', action='store_false', default=True,
                       dest='files', help='Skip retrieving files from store')

    jenkins = parser.add_argument_group('Jenkins', 'Jenkins configuration')
    jenkins.add_argument('--job', default=config.get('importer', 'job'),
                         help='Jenkins job to retrieve artifacts from')
    jenkins.add_argument('--artifact',
                         default=config.get('importer', 'artifact'),
                         help='Path to the dist directory artifact')
    jenkins.add_argument('--branch', default=config.get('importer', 'branch'),
                         help='Branch name to retrieve build artifact for')
    jenkins.add_argument('--results', default=config.get('importer', 'results'),
                         nargs='+', help='Build results to consider successful')
    jenkins.add_argument('--jenkins-username', dest='jenkins_username',
                         default=username,
                         help='Username to log into the Jenkins instance')
    jenkins.add_argument('--jenkins-password', dest='jenkins_password',
                         default=password,
                         help='Password to log into the Jenkins instance')
    jenkins.add_argument('--verify', nargs='?', const=True, default=verify,
                         help='Enable SSL cerificate verification')
    jenkins.add_argument('--no-verify', action='store_false', dest='verify',
                         help='Disable SSL cerificate verification')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)

    return args

def get_jenkins_url(args: Namespace) -> str:
    """
    Retrieve a URL from Jenkins using the build job API.
    """

    jenkins = Jenkins(args.jenkins, username=args.jenkins_username,
                      password=args.jenkins_password,
                      verify=args.verify)

    job = jenkins.get_job(args.job)
    if job.jobs:
        # Multibranch pipeline job
        job = job.get_job(args.branch)

    build = job.get_last_branch_build(args.branch)[0]
    if build is None:
        logging.warning('Could not find last build for branch %s', args.branch)
        build = job.last_build

    if isinstance(args.results, (list, tuple)):
        results = args.results
    else:
        results = args.results.split(',')

    if build.result not in results:
        raise ValueError('Build result is not {} but {}'.format(' or '.join(results), build.result))

    return f'{build.base_url}artifact/{args.artifact}/*zip*/dist.zip'

def copy_path(source_path: str, destination: str) -> None:
    """
    Copy a distribution directory from a local path.
    """

    dist_path = Path(source_path).expanduser() / 'dist'
    dest_path = Path(destination).resolve()
    if not dist_path.exists():
        raise OSError(f'Could not find distribution in {dist_path}')

    if dest_path.exists():
        if dest_path.samefile('.'):
            raise OSError('Refusing to delete the current working directory')

        shutil.rmtree(str(dest_path))

    shutil.copytree(str(dist_path), str(dest_path))

def download_zip(url: str, destination: str) -> None:
    """
    Download a ZIP archive from an external URL.
    """

    request = Session().get(url)
    request.raise_for_status()
    dist_path = Path('dist.zip')
    dest_path = Path(destination)
    with dist_path.open('wb') as output_file:
        for chunk in request.iter_content(chunk_size=128):
            output_file.write(chunk)

    temp_path = Path(tempfile.mkdtemp())
    with ZipFile(dist_path, 'r') as dist_zip:
        dist_zip.extractall(path=temp_path)

    try:
        if dist_path.exists():
            dist_path.unlink()
    except OSError:
        logging.exception('Could not remove distribution ZIP archive')

    lib_path = dest_path / 'lib'
    if lib_path.exists():
        shutil.rmtree(str(lib_path))

    shutil.move(str(temp_path / 'dist' / 'importerjson.jar'),
                str(dest_path / 'importerjson.jar'))
    shutil.move(str(temp_path / 'dist' / 'lib'), str(dest_path))
    shutil.rmtree(str(temp_path))

def retrieve_files(args: Namespace) -> None:
    """
    Retrieve the distribution files and store then within the dist directory.
    """

    if args.path is not None:
        try:
            copy_path(args.path, args.base)
        except OSError:
            logging.exception('Could not retrieve distribution')
            return
    else:
        # Use an URL to download a dist directory artifact archive
        if args.jenkins is None:
            url = args.url
        else:
            try:
                url = get_jenkins_url(args)
            except EnvironmentError:
                logging.exception('Could not log in to Jenkins')
                return
            except ValueError:
                logging.exception('Could not parse Jenkins job build data')
                return

        logging.info('Downloading distribution from %s', url)
        try:
            download_zip(url, args.base)
        except (ConnectError, HTTPError, Timeout):
            logging.exception('Could not download ZIP file')

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()
    retrieve_files(args)

    if args.files:
        store_type = File_Store.get_type(args.type)
        store = store_type(args.store)
        store.login(args.username, args.password)

        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            path = tmpfile.name

        data_file = 'data_vcsdev_to_dev.json'
        data_path = Path(args.base, data_file)
        # Retrieve the file from the store and write it to a temporary file
        store.get_file(f'import/{data_file}', path)
        if args.force or not data_path.exists() or \
            filecmp.cmp(str(data_path), path):
            shutil.move(path, str(data_path))
        else:
            raise RuntimeError(f'Not overwriting potentially updated file {data_file}')

if __name__ == "__main__":
    main()
