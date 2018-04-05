"""
Script used for initializing projects on a GitLab in order to prepare an import
of filtered source code into the projects.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
import logging
import os
import subprocess
import gitlab3
from gatherer.config import Configuration
from gatherer.domain import Project, Source
from gatherer.git import Git_Repository
from gatherer.log import Log_Setup

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()

    description = "Initialize repositories for filtered or archived source code storage"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")

    parser.add_argument("--repos", default=None, nargs='*',
                        help="custom list of repository names to process")

    gitlab = parser.add_argument_group('gitlab', 'GitLab upload')
    gitlab.add_argument("--url", default=config.get('gitlab', 'url'),
                        help="GitLab instance URL to upload to")
    gitlab.add_argument("--token", default=config.get('gitlab', 'token'),
                        help="GitLab token of group owner or admin")

    gitlab.add_argument("--user", default=config.get('gitlab', 'user'),
                        help="user to add to the GitLab group")
    gitlab.add_argument("--no-user", action="store_false", dest="user",
                        help="do not add user to GitLab group")
    gitlab.add_argument("--level", default=config.get('gitlab', 'level'),
                        type=int,
                        help="GitLab group access level to give to the user")

    agent = parser.add_argument_group('agent', 'Agent controller upload')
    agent.add_argument('--ssh', default=config.get('ssh', 'host'),
                       help='host name of the ssh server')
    agent.add_argument('--key', default='~/.ssh/id_rsa',
                       help='local path of the private key of the agent')
    agent.add_argument('--cert', default=config.get('ssh', 'cert'),
                       help='HTTPS certificate of the ssh server')

    bfg = parser.add_argument_group('bfg', 'BFG filtering')
    bfg.add_argument("--bfg", default=None,
                     help='BFG program to filter with')
    bfg.add_argument("--filter", default=None,
                     help='Filter file to use')

    parser.add_argument("--dry-run", default=False, action="store_true",
                        dest="dry_run",
                        help="Log what would be done without doing it")

    action = parser.add_mutually_exclusive_group()
    action.add_argument("--delete", default=False, action="store_true",
                        help="delete the repositories instead of creating them")
    action.add_argument("--create", default=False, action="store_true",
                        help="create empty repository on GitLab")
    action.add_argument("--upload", default=False, action="store_true",
                        help="upload from local repository to GitLab")
    action.add_argument("--agent", default=False, nargs='?',
                        const=config.get('ssh', 'username'),
                        help="upload from local repository to controller store")

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

class Repository_Archive(object):
    """
    Class that provides different actions that can be taken on an archiveable
    repository.
    """

    def __init__(self, project, git_repo, gitlab_api=None, dry_run=False):
        self._project = project
        self._repo = git_repo

        self._api = gitlab_api
        self._group = None

        self._dry_run = dry_run
        if self._dry_run:
            self._dry_run_log = 'Dry run: '
        else:
            self._dry_run_log = ''

    @property
    def repo_url(self):
        """
        Retrieve the URL to which the repository is archived.
        """

        return self._repo.source.url

    @property
    def repo_path(self):
        """
        Retrieve the path to the directory in which the repository is cloned.
        """

        return self._repo.repo_directory

    @property
    def repo_name(self):
        """
        Retrieve the GitLab project name that is used to archive the repository
        under.
        """

        return self._repo.source.name

    @property
    def api(self):
        """
        Retrieve an API connection to the GitLab archive location.
        """

        if self._api is None:
            raise RuntimeError('Cannot access the GitLab API')

        return self._api

    @property
    def group(self):
        """
        Retrieve a GitLab API instance for the project's archive location.
        """

        if self._group is None:
            # pylint: disable=no-member
            name = self._project.gitlab_group_name
            self._group = self.api.group(name)
            if not self._group:
                raise RuntimeError('Group {} not found on GitLab'.format(name))

        return self._group

    def delete(self):
        """
        Delete an existing repository from GitLab if it exists.
        """

        project_name = self._project.gitlab_group_name
        path = '{0}/{1}'.format(project_name, self.repo_name.lower())
        project_repo = self.api.find_project(path_with_namespace=path)
        if project_repo:
            if not self._dry_run:
                self.api.delete_project(project_repo)

            logging.info('%sDeleted repository %s', self._dry_run_log, path)
        else:
            logging.warning('Could not find repository %s', path)

    def create(self):
        """
        Create a new repository in GitLab if it did not already exist.
        """

        project_name = self._project.gitlab_group_name
        path = '{0}/{1}'.format(project_name, self.repo_name.lower())
        project_repo = self.api.find_project(path_with_namespace=path)
        if project_repo:
            logging.warning('Repository for %s already exists', path)
        else:
            if not self._dry_run:
                new_project_repo = self.api.add_project(self.repo_name)
                new_project_repo.unprotect_branch('master')
                self.group.transfer_project(new_project_repo.id)

            logging.info('%sCreated repository %s/%s', self._dry_run_log,
                         project_name, self.repo_name)

    def upload(self):
        """
        Upload a local repository to the archived repository.
        """

        if not self._repo.exists():
            logging.warning('Cannot find local repository %s', self.repo_path)
        else:
            if not self._dry_run:
                self._repo.repo.remotes.origin.set_url(self.repo_url)
                self._repo.repo.remotes.origin.push()

            logging.info('%sUploaded local repository to %s', self._dry_run_log,
                         self.repo_url)

    def update_user(self, user_name, level):
        """
        Add a user with the correct access level to the group membership.
        """

        user = self.api.find_user(name=user_name)
        if not user:
            logging.warning('No existing user to be added to group membership')
            return

        if self.group.find_member(id=user.id, access_level=level):
            logging.info('User is already part of the group membership')
        else:
            if not self._dry_run:
                self.group.add_member(user.id, level)

            logging.info('%sAdded user to the group membership',
                         self._dry_run_log)

    def filter_sourcecode(self, bfg_path, filter_path):
        """
        Use BFG to filter the source code in each revision of the repository
        cloned at `repo_path`.
        """

        logging.info('%sExecuting BFG to filter source code on %s',
                     self._dry_run_log, self.repo_path)
        if not self._dry_run:
            try:
                output = subprocess.check_output([
                    'java', '-jar', bfg_path, '--replace-text', filter_path,
                    '--no-blob-protection', self.repo_path
                ], stderr=subprocess.STDOUT)
                logging.info(output)
            except subprocess.CalledProcessError as error:
                logging.error(error.output)
                raise

    def upload_agent(self, agent, ssh, key_path):
        """
        Upload the repository to the controller server for later archival.
        """

        logging.info('Bundle repository %s for agent upload', self.repo_path)
        bundle_name = '{}.bundle'.format(self.repo_name)
        bundle_path = os.path.abspath(os.path.join(self._project.export_key,
                                                   bundle_name))
        self._repo.repo.git.bundle(['create', bundle_path, '--all'])

        if not self._dry_run:
            auth = agent + '@' + ssh
            path = '{}:~/{}'.format(auth, self._project.export_key)
            subprocess.call(['scp', '-i', key_path, bundle_path, path])

        logging.info('%sUploaded bundle to controller', self._dry_run_log)

def get_git_repositories(project, repo_directory, repo_names=None):
    """
    Retrieve all immediate directories containing git repositories as well as
    all repositories in subdirectories.
    """

    repos = []
    found_names = set()
    for source in project.sources:
        if repo_names is None or source.path_name in repo_names:
            path = os.path.join(repo_directory, source.path_name)
            repo = Git_Repository.from_source(source, path, project=project)
            if repo.exists():
                repos.append(repo)
                found_names.add(source.path_name)

    if repo_names is not None:
        missing_names = set(repo_names) - found_names
        if missing_names:
            logging.warning('Missing source information for repositories: %s',
                            ', '.join(missing_names))

    return repos

def main():
    """
    Main entry point.
    """

    args = parse_args()
    project_key = args.project
    project = Project(project_key)
    project_name = project.gitlab_group_name
    if project_name is None:
        logging.warning('Cannot determine GitLab group name')
        return

    if args.dry_run:
        logging.info('Dry run: No actions are actually performed')

    repo_directory = os.path.join('project-git-repos', project_key)
    project_repos = get_git_repositories(project, repo_directory, args.repos)

    logging.info('%s: %s (%d repos)',
                 project_key, project_name, len(project_repos))

    if args.delete or args.create or args.upload:
        api = gitlab3.GitLab(args.url, args.token)
    else:
        api = None

    for repo in project_repos:
        logging.info('Processing repository %s', repo.repo_name)
        repo_name = repo.repo_name.lower().replace('/', '-')
        repo_path = os.path.join(repo_directory, repo_name)
        git_url = '{0}{1}/{2}.git'.format(args.url, project.gitlab_group_name,
                                          repo_name)
        source = Source.from_type('git', name=repo_name, url=git_url)
        git_repo = Git_Repository(source, repo_path)

        archive = Repository_Archive(project, git_repo, gitlab_api=api,
                                     dry_run=args.dry_run)

        if args.bfg:
            archive.filter_sourcecode(args.bfg, args.filter)

        if args.delete:
            archive.delete()
        if args.create or args.upload:
            archive.create()
            if args.upload:
                archive.upload()

        if args.user:
            archive.update_user(args.user, args.level)

        if args.agent:
            archive.upload_agent(args.agent, args.ssh, args.key)

if __name__ == "__main__":
    main()
