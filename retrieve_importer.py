"""
Script for downloading the Java database importer from a URL and extracting it
such that the Jenkins scraper can run all programs.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
import filecmp
import logging
import os
import shutil
import tempfile
from zipfile import ZipFile
# Not-standard imports
from gatherer.config import Configuration
from gatherer.files import File_Store
from gatherer.jenkins import Jenkins
from gatherer.log import Log_Setup
from gatherer.request import Session

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    verify = config.get('jenkins', 'verify')
    if not Configuration.has_value(verify):
        verify = False
    elif not os.path.exists(verify):
        verify = True

    username = config.get('jenkins', 'username')
    password = config.get('jenkins', 'password')
    if not Configuration.has_value(username):
        username = None
        password = None

    description = 'Retrieve the database importer and auxiliary data'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--base', default='.',
                        help='directory to place the importer and libraries in')
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

def get_jenkins_url(args):
    """
    Retrieve an URL from Jenkins using the build job API.
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

    return build.base_url + 'artifact/' + args.artifact + '/*zip*/dist.zip'


def main():
    """
    Main entry point.
    """

    args = parse_args()
    if args.path is not None:
        shutil.copytree(os.path.join(os.path.expanduser(args.path), 'dist/'),
                        'dist/')
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
        request = Session().get(url)
        with open('dist.zip', 'wb') as output_file:
            for chunk in request.iter_content(chunk_size=128):
                output_file.write(chunk)

        with ZipFile('dist.zip', 'r') as dist_zip:
            dist_zip.extractall()

        os.remove('dist.zip')

    # Check if 'dist' is the directory we want to place it in
    if os.path.realpath(args.base) == os.path.realpath('dist'):
        return

    if os.path.exists(os.path.join(args.base, 'lib')):
        shutil.rmtree(os.path.join(args.base, 'lib'))

    shutil.move('dist/importerjson.jar',
                os.path.join(args.base, 'importerjson.jar'))
    shutil.move('dist/lib/', args.base)
    shutil.rmtree('dist')

    if args.files:
        store_type = File_Store.get_type(args.type)
        store = store_type(args.store)
        store.login(args.username, args.password)

        path = tempfile.mktemp()
        data_file = 'data_vcsdev_to_dev.json'
        data_path = os.path.join(args.base, data_file)
        store.get_file('import/{}'.format(data_file), path)
        if not os.path.exists(data_path) or filecmp.cmp(data_path, path):
            shutil.move(path, data_path)
        else:
            raise RuntimeError('Not overwriting potentially updated file {}'.format(data_file))

if __name__ == "__main__":
    main()
