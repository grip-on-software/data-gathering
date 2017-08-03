"""
Module that handles access to and remote updates of a Git repository.
"""

from builtins import str
import datetime
from io import BytesIO
import logging
import os
import re
import tempfile
from git import Git, Repo, Blob, Commit, InvalidGitRepositoryError, NoSuchPathError, NULL_TREE
from ordered_set import OrderedSet
from .progress import Git_Progress
from ..table import Table, Key_Table
from ..utils import convert_local_datetime, format_date, parse_unicode, Iterator_Limiter
from ..version_control.repo import Change_Type, Version_Control_Repository, FileNotFoundException

class Sparse_Checkout_Paths(object):
    """
    Reader and writer for the sparse checkout information file that tracks which
    paths should be checked out in a sparse checkout of the repository.

    """

    # Path within the git configuration directory.
    PATH = 'info'
    # File name of the information file.
    FILE = 'sparse-checkout'

    def __init__(self, repo):
        self._repo = repo
        self._path = os.path.join(self._repo.git_dir, self.PATH, self.FILE)

    def get(self):
        """
        Retrieve the current list of paths to check out from the sparse checkout
        information file.
        """

        if os.path.exists(self._path):
            with open(self._path) as sparse_file:
                return OrderedSet(sparse_file.read().split('\n'))

        return OrderedSet()

    def _write(self, paths):
        with open(self._path, 'w') as sparse_file:
            sparse_file.write('\n'.join(paths))

    def set(self, paths, append=True):
        """
        Accept paths in the local clone by updating the paths to check out in
        the sparse checkout information file.

        If `append` is `True`, the unique paths stored previosly in the file
        are kept, otherwise they are overwritten.
        """

        if append:
            original_paths = self.get()
        else:
            original_paths = OrderedSet()

        self._write(original_paths | paths)

    def remove(self, paths):
        """
        Remove paths to check out in the sparse checkout information file.
        """

        new_paths = self.get()
        if not new_paths:
            new_paths = OrderedSet(['/*'])

        for path in paths:
            if path in new_paths:
                new_paths.remove(path)
            else:
                new_paths.add('!{}'.format(path))

        self._write(new_paths)

class Git_Repository(Version_Control_Repository):
    """
    A single Git repository that has commit data that can be read.
    """

    DEFAULT_UPDATE_RATIO = 10
    BATCH_SIZE = 10000
    LOG_SIZE = 1000

    MERGE_PATTERNS = tuple(re.compile(pattern) for pattern in (
        r".*\bMerge branch '([^']+)'",
        r".*\bMerge remote-tracking branch '(?:(?:refs/)?remotes)?origin/([^']+)'",
        r"Merge pull request \d+ from ([^\s]+) into .+",
        r"([A-Z]{3,}\d+) [Mm]erge",
        r"(?:Merge )?([^\s]+) >\s?master"
    ))

    def __init__(self, source, repo_directory, progress=None, **kwargs):
        super(Git_Repository, self).__init__(source, repo_directory, **kwargs)
        self._repo = None
        self._unsafe_hosts = bool(source.get_option('unsafe'))
        self._from_date = source.get_option('from_date')
        self._tag = source.get_option('tag')

        # If `progress` is `True`, then add progress lines from Git commands to
        # the logging output. If `progress` is a nonzero number, then sample
        # from this number of lines. If it is not `False`, then use it as
        # a progress callback function.
        if progress is True:
            self._progress = Git_Progress(update_ratio=self.DEFAULT_UPDATE_RATIO)
        elif isinstance(progress, int) and progress > 0:
            self._progress = Git_Progress(update_ratio=progress)
        else:
            self._progress = None

        self._iterator_limiter = None
        self._reset_limiter()
        self._tables.update({
            'change_path': Table('change_path'),
            'tag': Key_Table('tag', 'tag_name',
                             encrypt_fields=('tagger', 'tagger_email'))
        })

    def _reset_limiter(self):
        self._iterator_limiter = Iterator_Limiter(size=self.BATCH_SIZE)

    def _get_refspec(self, from_revision=None, to_revision=None):
        # Determine special revision ranges from credentials settings.
        # By default, we retrieve all revisions from master, but if the tag
        # exists, then we use this tag as end point instead. Otherwise, the
        # range can be limited by a starting date for migration compatibility.
        default_to_revision = 'master'
        if self._tag is not None and self._tag in self.repo.tags:
            default_to_revision = self._tag
        elif from_revision is None and self._from_date is not None:
            from_revision = ''.join(('@', '{', self._from_date, '}'))

        # Format the range as a specifier that git rev-parse can handle.
        if from_revision is not None:
            if to_revision is not None:
                return '{}...{}'.format(from_revision, to_revision)

            return '{}...{}'.format(from_revision, default_to_revision)

        if to_revision is not None:
            return to_revision

        return default_to_revision

    @classmethod
    def from_source(cls, source, repo_directory, **kwargs):
        """
        Initialize a Git repository from its `Source` domain object.

        Returns a Git_Repository object with a cloned and up-to-date repository,
        even if the repository already existed beforehand.

        The keyword arguments may optionally include `checkout`. If this is
        not given or it is set to `False`, then the local directory does not
        contain the actual paths and files from the repository, similar to
        a bare checkout (except that the tree can be made intact again).
        A value of `True` checks out the entire repository as on a normal clone
        or pull. If `checkout` receives a list, then the paths in this list
        are added to a sparse checkout, and updated from the remote.

        Another optional keyword argument is `shallow`. If it is set to `True`,
        then the local directory only contains the default branch's head commit
        after cloning. Note that no precautions are made to prevent pulling in
        more commits unless `shallow` is provided to each action.
        """

        checkout = kwargs.pop('checkout', False)
        shallow = kwargs.pop('shallow', False)
        repository = cls(source, repo_directory, **kwargs)
        if os.path.exists(repo_directory):
            if not repository.is_empty():
                if isinstance(checkout, list):
                    repository.checkout_sparse(checkout, shallow=shallow)
                else:
                    repository.update(shallow=shallow)
        elif isinstance(checkout, bool):
            repository.clone(checkout=checkout, shallow=shallow)
        else:
            repository.checkout(paths=checkout, shallow=shallow)

        return repository

    @property
    def repo(self):
        if self._repo is None:
            # Use property setter for updating the environment credentials path
            self.repo = Repo(self._repo_directory)

        return self._repo

    @repo.setter
    def repo(self, repo):
        if not isinstance(repo, Repo):
            raise TypeError('Repository must be a gitpython Repo instance')

        repo.git.update_environment(**self._create_environment(repo))
        self._repo = repo

    def _create_environment(self, repo=None):
        """
        Retrieve the environment variables for the Git subcommands.
        """

        environment = {}

        credentials_path = self.source.credentials_path
        if credentials_path is not None:
            logging.debug('Using credentials path %s', credentials_path)
            ssh_command = "ssh -i '{}'".format(credentials_path)
            if self._unsafe_hosts:
                ssh_command += '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'

            if repo is not None:
                version_info = repo.git.version_info
            else:
                version_info = Git().version_info

            if version_info < (2, 3, 0):
                with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
                    tmpfile.write(ssh_command + ' $*')
                    command_filename = tmpfile.name

                os.chmod(command_filename, 0o700)
                environment['GIT_SSH'] = command_filename
                logging.debug('Command filename: %s', command_filename)
            else:
                environment['GIT_SSH_COMMAND'] = ssh_command

        return environment

    @property
    def version_info(self):
        return self.repo.git.version_info

    def exists(self):
        """
        Check whether the repository exists, i.e., the path points to a valid
        Git repository.
        """

        try:
            return bool(self.repo)
        except (InvalidGitRepositoryError, NoSuchPathError):
            return False

    def is_empty(self):
        """
        Check whether the repository is empty, i.e. no commits have been made
        at all.
        """

        return not self.repo.branches

    def update(self, shallow=False):
        # Update the repository from the origin URL.
        if shallow:
            self.repo.remotes.origin.fetch('master', depth=1,
                                           progress=self._progress)
            self.repo.head.reset('origin/master', hard=True)
            self.repo.git.reflog(['expire', '--expire=now', '--all'])
            self.repo.git.gc(['--prune=now'])
        else:
            self.repo.remotes.origin.pull('master', progress=self._progress)

    def checkout(self, paths=None, shallow=False):
        self.clone(checkout=paths is None, shallow=shallow)

        if paths is not None:
            self.checkout_sparse(paths, shallow=shallow)

    def checkout_sparse(self, paths, remove=False, shallow=False):
        self.repo.config_writer().set_value('core', 'sparseCheckout', True)
        sparse = Sparse_Checkout_Paths(self.repo)

        if remove:
            sparse.remove(paths)
        else:
            sparse.set(paths)

        # Now checkout the sparse directories.
        self.repo.git.read_tree(['-m', '-u', 'HEAD'])

        # Ensure repository is up to date.
        self.update(shallow=shallow)

    def clone(self, checkout=True, shallow=False):
        """
        Clone the repository, optionally according to a certain checkout
        scheme. If `checkout` is `False`, then do not check out the local files
        of the default branch (all repository actions still function).
        If `shallow` is `True`, then only the default branch's head commit is
        fetched. Note that not precautions are made to prevent pulling in more
        commits later on unless `shallow` is used for all actions.
        """

        kwargs = {
            "no_checkout": not checkout
        }
        if shallow:
            kwargs["depth"] = 1

        self.repo = Repo.clone_from(self.source.url, self.repo_directory,
                                    progress=self._progress,
                                    env=self._create_environment(),
                                    **kwargs)

    def _query(self, refspec, paths='', descending=True):
        return self.repo.iter_commits(refspec, paths=paths,
                                      max_count=self._iterator_limiter.size,
                                      skip=self._iterator_limiter.skip,
                                      reverse=not descending)

    def find_commit(self, committed_date):
        """
        Find a commit SHA by its committed date, assuming the date is unique.

        If the commit could not be found, then `None` is returned.
        """

        date_epoch = committed_date.strftime('%s')
        rev_list_args = {
            'max_count': 1,
            'min_age': date_epoch,
            'max_age': date_epoch
        }
        commits = list(self.repo.iter_commits('master', **rev_list_args))
        if commits:
            return commits[0].hexsha

        return None

    def get_versions(self, filename='', from_revision=None, to_revision=None,
                     descending=False, **kwargs):
        refspec = self._get_refspec(from_revision, to_revision)
        return self._parse(refspec, paths=filename, descending=descending, **kwargs)

    def get_data(self, from_revision=None, to_revision=None, **kwargs):
        versions = super(Git_Repository, self).get_data(from_revision,
                                                        to_revision, **kwargs)

        self._parse_tags()

        return versions

    def _parse(self, refspec, paths='', descending=True, **kwargs):
        self._reset_limiter()

        version_data = []
        commits = self._query(refspec, paths=paths, descending=descending)
        had_commits = True
        count = 0
        while self._iterator_limiter.check(had_commits):
            had_commits = False

            for commit in commits:
                had_commits = True
                count += 1
                version_data.append(self._parse_version(commit, **kwargs))

                if count % self.LOG_SIZE == 0:
                    logging.info('Analysed commits up to %d', count)

            logging.info('Analysed batch of commits, now at %d', count)

            self._iterator_limiter.update()

            if self._iterator_limiter.check(had_commits):
                commits = self._query(refspec, paths=paths, descending=descending)

        return version_data

    def _parse_version(self, commit, stats=True, **kwargs):
        """
        Convert one commit instance to a dictionary of properties.
        """

        commit_datetime = convert_local_datetime(commit.committed_datetime)
        author_datetime = convert_local_datetime(commit.authored_datetime)

        commit_type = str(commit.type)
        if len(commit.parents) > 1:
            commit_type = 'merge'

        developer = parse_unicode(commit.author.name)
        git_commit = {
            # Primary data
            'repo_name': str(self._repo_name),
            'version_id': str(commit.hexsha),
            'sprint_id': self._get_sprint_id(commit_datetime),
            # Additional data
            'message': parse_unicode(commit.message),
            'type': commit_type,
            'developer': developer,
            'developer_username': developer,
            'developer_email': str(commit.author.email),
            'commit_date': format_date(commit_datetime),
            'author_date': format_date(author_datetime)
        }

        if stats:
            git_commit.update(self._get_diff_stats(commit))
            git_commit['branch'] = self._get_original_branch(commit)
            self._parse_change_stats(commit)

        return git_commit

    @staticmethod
    def _get_diff_stats(commit):
        cstotal = commit.stats.total

        return {
            # Statistics
            'insertions': str(cstotal['insertions']),
            'deletions': str(cstotal['deletions']),
            'number_of_files': str(cstotal['files']),
            'number_of_lines': str(cstotal['lines']),
            'size': str(commit.size)
        }

    def _get_original_branch(self, commit):
        commits = self.repo.iter_commits('{}..HEAD'.format(commit.hexsha),
                                         ancestry_path=True, merges=True,
                                         reverse=True)

        try:
            merge_commit = next(commits)
        except StopIteration:
            return str(0)

        merge_message = parse_unicode(merge_commit.message)
        for pattern in self.MERGE_PATTERNS:
            match = pattern.match(merge_message)
            if match:
                return match.group(1)

        return str(0)

    @staticmethod
    def _format_replaced_path(old_path, new_path):
        # Not implemented: C-style quoted files with non-unicode characters
        # Find common prefix
        prefix_length = 0
        for index, pair in enumerate(zip(old_path, new_path)):
            if pair[0] != pair[1]:
                break
            if pair[0] == '/':
                prefix_length = index + 1

        # Find common suffix
        suffix_length = 0
        prefix_adjust_for_slash = 1 if prefix_length else 0
        old_index = len(old_path) - 1
        new_index = len(new_path) - 1
        while prefix_length - prefix_adjust_for_slash <= old_index and \
                prefix_length - prefix_adjust_for_slash <= new_index and \
                old_path[old_index] == new_path[new_index]:
            if old_path[old_index] == '/':
                suffix_length = len(old_path) - old_index

            old_index -= 1
            new_index -= 1

        # Format replaced path
        old_midlen = max(0, len(old_path) - suffix_length)
        new_midlen = max(0, len(new_path) - suffix_length)

        mid_name = old_path[prefix_length:old_midlen] + ' => ' + \
                new_path[prefix_length:new_midlen]
        if prefix_length + suffix_length > 0:
            return old_path[:prefix_length] + '{' + mid_name + '}' + \
                    old_path[len(old_path)-suffix_length:]

        return mid_name

    def _parse_change_stats(self, commit):
        if commit.parents:
            parent_diffs = tuple(commit.diff(parent, R=True) for parent in commit.parents)
        else:
            parent_diffs = (commit.diff(NULL_TREE),)

        for diffs in parent_diffs:
            self._parse_change_diffs(commit, diffs)

    def _parse_change_diffs(self, commit, diffs):
        files = commit.stats.files
        for diff in diffs:
            old_file = diff.a_path
            new_file = diff.b_path
            change_type = Change_Type.from_label(diff.change_type)
            if old_file != new_file:
                stat_file = self._format_replaced_path(old_file, new_file)
            else:
                stat_file = old_file

            if stat_file not in files:
                logging.debug('File change %s in commit %s has no stats',
                              stat_file, commit.hexsha)
                continue

            insertions = files[stat_file]['insertions']
            deletions = files[stat_file]['deletions']

            change_data = {
                'repo_name': str(self._repo_name),
                'version_id': str(commit.hexsha),
                'file': str(new_file),
                'change_type': str(change_type.value),
                'insertions': str(insertions),
                'deletions': str(deletions)
            }
            self._tables['change_path'].append(change_data)

    def _parse_tags(self):
        for tag_ref in self.repo.tags:
            tag_data = {
                'repo_name': str(self._repo_name),
                'tag_name': tag_ref.name,
                'version_id': str(tag_ref.commit.hexsha),
                'message': str(0),
                'tagged_date': str(0),
                'tagger': str(0),
                'tagger_email': str(0)
            }
            if tag_ref.tag is not None:
                tag_data['message'] = parse_unicode(tag_ref.tag.message)

                tag_timestamp = tag_ref.tag.tagged_date
                tagged_datetime = datetime.datetime.fromtimestamp(tag_timestamp)
                tag_data['tagged_date'] = format_date(tagged_datetime)

                tag_data['tagger'] = parse_unicode(tag_ref.tag.tagger.name)
                tag_data['tagger_email'] = str(tag_ref.tag.tagger.email)

            self._tables['tag'].append(tag_data)

    def get_latest_version(self):
        return self.repo.rev_parse('master').hexsha

    def get_contents(self, filename, revision=None):
        if isinstance(revision, Commit):
            commit = revision
        elif revision is not None:
            commit = self.repo.commit(revision)
        else:
            commit = self.repo.commit('HEAD')

        try:
            blob = commit.tree.join(filename)
        except KeyError as error:
            raise FileNotFoundException(str(error))

        if not isinstance(blob, Blob):
            raise FileNotFoundException('Path {} has no Blob object'.format(filename))

        stream = BytesIO()
        blob.stream_data(stream)
        return stream.getvalue()
