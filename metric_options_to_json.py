"""
Script to parse historical project definitions and extract metric targets from
these versions into JSON output.
"""

import argparse
import ConfigParser
import datetime
import inspect
import json
import os.path
import sys
import traceback
# Non-standard imports
import dateutil.tz
import mock
import svn.local
from hqlib import domain, metric

# Define some classes that are backward compatible with earlier versions of
# hqlib (quality_report, qualitylib). This suppresses argument exceptions.
class Compatibility(object):
    """
    Handler for classes that are backward compatible with earlier versions
    of those classes in distributed modules.
    """

    replacements = {}

    @classmethod
    def replaces(cls, target):
        """
        Decorator method for a class that replaces another class `target`.
        """

        def decorator(subject):
            """
            Decorator that registers the class `subject` as a replacement.
            """

            cls.replacements[target] = subject
            return subject

        return decorator

    @classmethod
    def get_replacement(cls, name, member):
        """
        Find a suitable replacement for a class whose interface should be
        mostly adhered, but its functionality should not be executed.
        """

        if member in cls.replacements:
            return cls.replacements[member]

        replacement = mock.Mock(name=name, spec_set=member)
        replacement.configure_mock(name=name)
        return replacement

@Compatibility.replaces(domain.TechnicalDebtTarget)
class TechnicalDebtTarget(domain.TechnicalDebtTarget):
    # pylint: disable=missing-docstring,too-few-public-methods,unused-argument
    def __init__(self, target_value, explanation='', unit=''):
        super(TechnicalDebtTarget, self).__init__(target_value, explanation)

@Compatibility.replaces(domain.DynamicTechnicalDebtTarget)
class DynamicTechnicalDebtTarget(domain.DynamicTechnicalDebtTarget):
    # pylint: disable=missing-docstring,too-few-public-methods,unused-argument
    # pylint: disable=too-many-arguments
    def __init__(self, initial_target_value, initial_datetime,
                 end_target_value, end_datetime, explanation='', unit=''):
        parent = super(DynamicTechnicalDebtTarget, self)
        parent.__init__(initial_target_value, initial_datetime,
                        end_target_value, end_datetime, explanation)

class Project_Definition_Parser(object):
    """
    Parser for project definitions of the quality reporting tool.
    """

    DOMAIN = 'hqlib.domain'

    def __init__(self, context_lines=3, file_time=None):
        self.context_lines = context_lines
        self.file_time = file_time

        self.domain_objects = self.get_mock_domain_objects()
        self.metric_targets = {}
        self.old_metric_options = {
            'low_targets': 'low_target',
            'targets': 'target',
            'technical_debt_targets': 'debt_target'
        }

    def filter_member(self, member):
        """
        Check whether a given member of a module is within the domain of objects
        that we need to mock or replace to be able to read the project
        definition.
        """

        if inspect.isclass(member) and member.__module__.startswith(self.DOMAIN):
            return True

        return False

    def get_mock_domain_objects(self):
        """
        Create a dictionary of class names and their mocks and replacements.

        These classes live within the quality reporting domain module.
        """

        domain_objects = {}
        for name, member in inspect.getmembers(domain, self.filter_member):
            replacement = Compatibility.get_replacement(name, member)
            domain_objects[name] = replacement

        return domain_objects

    def format_exception(self, contents, emulate_context=True):
        """
        Handle a problem parsing the project definition `content` from within
        an exception context.
        """

        etype, value, trace = sys.exc_info()
        formatted_lines = traceback.format_exception_only(etype, value)
        message = "Could not parse project definition: " + formatted_lines[-1]
        if self.context_lines >= 0:
            message += ''.join(formatted_lines[:-1])
            if emulate_context:
                line = traceback.extract_tb(trace)[-1][1]
                lines = contents.split('\n')
                range_start = max(0, line-self.context_lines-1)
                range_end = min(len(lines), line+self.context_lines)
                message += "Context:\n" + '\n'.join(lines[range_start:range_end])

        raise RuntimeError(message.strip())

    def load_definition(self, contents):
        """
        Safely read the contents of a project definition file.

        This uses patching and mocks to avoid loading external repositories
        through the quality reporting framework and to skip internal information
        that we do not need.
        """

        # Mock all imports made by project definitions to safely read it.
        ictu = mock.MagicMock()
        convention = mock.MagicMock()
        metric_source = mock.MagicMock()
        hqlib = mock.MagicMock(metric=mock.MagicMock(**metric.__dict__))
        hqlib_domain = mock.MagicMock(**self.domain_objects)

        # Mock the internal source module (ictu, backwards compatible: isd) and
        # the reporting module (hqlib, backwards compatible: quality_report,
        # qualitylib) as well as the submodules that the project definition
        # imports.
        modules = {
            'ictu': ictu,
            'ictu.convention': convention,
            'ictu.metric_source': metric_source,
            'isd': ictu,
            'isd.convention': convention,
            'isd.metric_source': metric_source,
            'hqlib': hqlib,
            'hqlib.domain': hqlib_domain,
            'quality_report': hqlib,
            'quality_report.domain': hqlib_domain,
            'qualitylib': hqlib,
            'qualitylib.domain': hqlib_domain,
            'python.qualitylib': hqlib,
            'python.qualitylib.domain': hqlib_domain
        }
        open_mock = mock.mock_open()

        with mock.patch.dict('sys.modules', modules):
            with mock.patch('__main__.open', open_mock):
                # Load the project definition by executing the contents of
                # the file with altered module definitions. This should be safe
                # since all relevant modules and context has been patched.
                # pylint: disable=exec-used,broad-except
                try:
                    exec(contents)
                except SyntaxError as exception:
                    # Most syntax errors have correct line marker information
                    if exception.text is None:
                        self.format_exception(contents)
                    else:
                        self.format_exception(contents, emulate_context=False)
                except Exception:
                    # Because of string execution, the line number of the
                    # exception becomes incorrect. Attempt to emulate the
                    # context display using traceback extraction.
                    self.format_exception(contents)

    def parse(self):
        """
        Retrieve metric targets from the collected domain objects that were
        specified in the project definition.
        """

        for mock_object in self.domain_objects.itervalues():
            if isinstance(mock_object, domain.DomainObject):
                for call in mock_object.call_args_list:
                    keywords = call[1]
                    self.parse_domain_call(keywords)

        return self.metric_targets

    def parse_domain_call(self, keywords):
        """
        Retrieve metric targets from a singular call within the project
        definition, which may have redefined metric options.
        """

        if "name" in keywords:
            name = keywords["name"]
        else:
            name = ""

        if "metric_options" in keywords:
            for metric_type, options in keywords["metric_options"].iteritems():
                self.parse_metric(name, metric_type, options=options)

        for old_keyword, new_key in self.old_metric_options.iteritems():
            if old_keyword in keywords:
                for metric_type, option in keywords[old_keyword].iteritems():
                    self.parse_metric(name, metric_type,
                                      options={new_key: option},
                                      options_type='old_options')

    def parse_metric(self, name, metric_type, options, options_type='metric_options'):
        """
        Update the metric targets for a metric specified in the project
        definition.
        """

        if isinstance(metric_type, mock.Mock):
            class_name = metric_type.name
            if isinstance(class_name, mock.Mock):
                # pylint: disable=protected-access
                class_name = metric_type._mock_name
        else:
            class_name = metric_type.__name__

        metric_name = class_name + name
        if metric_name in self.metric_targets:
            targets = self.metric_targets[metric_name]
        elif isinstance(metric_type, mock.Mock):
            # No default data available
            targets = {
                'low_target': '0',
                'target': '0',
                'type': 'old_options',
                'comment': ''
            }
        else:
            targets = {
                'low_target': str(int(metric_type.low_target_value)),
                'target': str(int(metric_type.target_value)),
                'type': options_type,
                'comment': ''
            }

        for key in ('low_target', 'target', 'comment'):
            if key in options:
                targets[key] = str(options[key])

        targets.update(self.parse_debt_target(options))

        self.metric_targets[metric_name] = targets

    def parse_debt_target(self, options):
        """
        Retrieve data regarding a technical debt target.
        """

        if 'debt_target' in options:
            debt = options['debt_target']

            datetime_args = {'now.return_value': self.file_time}
            with mock.patch('datetime.datetime', **datetime_args):
                debt_target = debt.target_value()
                debt_comment = debt.explanation()

                return {
                    'target': str(debt_target),
                    'type': debt.__class__.__name__,
                    'comment': debt_comment
                }

        return {}

class Subversion_Repository(object):
    """
    Class representing a subversion repository from which files and their
    histories (contents, logs) can be read.
    """

    def __init__(self, path='.'):
        self.path = os.path.expanduser(path)
        self.svn = svn.local.LocalClient(self.path)

    def get_versions(self, filename, from_revision=None, to_revision=None, descending=False):
        """
        Retrieve data about each version of a specific file path `filename`.

        The range of the log to retrieve can be set with `from_revision` and
        `to_revision`, both are optional. The log is sorted by commit date,
        either newest first (`descending`) or not (default)
        """

        versions = []
        log = self.svn.log_default(rel_filepath=filename,
                                   revision_from=from_revision,
                                   revision_to=to_revision)
        for entry in log:
            # Convert to local timestamp
            commit_date = entry.date.replace(tzinfo=dateutil.tz.tzutc())
            commit_date = commit_date.astimezone(dateutil.tz.tzlocal())
            message = entry.msg if entry.msg is not None else ''
            version = {
                'revision': str(entry.revision),
                'developer': entry.author,
                'message': message,
                'commit_date': datetime.datetime.strftime(commit_date, '%Y-%m-%d %H:%M:%S')
            }

            versions.append(version)

        return sorted(versions, key=lambda version: version['revision'],
                      reverse=descending)

    def get_contents(self, filename, revision=None):
        """
        Retrieve the contents of a file with path `filename` at the given
        `revision`, or the currently checked out revision if not given.
        """

        return self.svn.cat(filename, revision=revision)

class Metric_Difference(object):
    """
    Class that determines whether metric options were changed.
    """

    def __init__(self, project_key, previous_targets=None):
        self._project_key = project_key
        if previous_targets is not None:
            self._previous_metric_targets = previous_targets
        else:
            self._previous_metric_targets = {}

        self._unique_versions = []
        self._unique_metric_targets = []

    def add_version(self, version, metric_targets):
        """
        Check whether this version contains unique changes.
        """

        # Detect whether the metrics and definitions have changed
        if metric_targets != self._previous_metric_targets:
            self._unique_versions.append(version)
            for name, metric_target in metric_targets.iteritems():
                if name in self._previous_metric_targets:
                    previous_metric_target = self._previous_metric_targets[name]
                else:
                    previous_metric_target = {}

                if metric_target != previous_metric_target:
                    unique_target = dict(metric_target)
                    unique_target['name'] = name
                    unique_target['revision'] = version['revision']
                    self._unique_metric_targets.append(unique_target)

            self._previous_metric_targets = metric_targets

    def export(self):
        """
        Save the unique data to JSON files.
        """

        with open(self._project_key + '/data_metric_versions.json', 'w') as out:
            json.dump(self._unique_versions, out, indent=4)

        with open(self._project_key + '/data_metric_targets.json', 'w') as out:
            json.dump(self._unique_metric_targets, out, indent=4)

    @property
    def previous_metric_targets(self):
        """
        Retrieve the previous metric targets, which need to be retained for
        later instances of this class.
        """

        return self._previous_metric_targets

    @property
    def unique_versions(self):
        """
        Retrieve the unique versions that have changed metric targets.
        """

        return self._unique_versions

    @property
    def unique_metric_targets(self):
        """
        Retrieve metric targets that changed within revisions.
        """

        return self._unique_metric_targets

class Update_Tracker(object):
    """
    Class that keeps track of the previous and current state of an incremental
    update, so that the data gatherer can resume from a previous known state.
    """

    def __init__(self, project_key):
        self._project_key = project_key
        self._filename = self._project_key + '/metric_options_update.json'

        self._file_loaded = False
        self._from_revision = None
        self._previous_targets = None

    def get_start_revision(self, from_revision=None):
        """
        Retrieve the revision from which we should retrieve new versions from.

        By default, this is the last revision that was parsed previously,
        but this can be overridden using `from_revision`.
        """

        if from_revision is not None:
            return from_revision

        if not self._file_loaded:
            self._read()

        if self._from_revision is None:
            return None

        return self._from_revision + 1

    def get_previous_targets(self):
        """
        Retrieve the metric targets of the latest unique revision that was
        parsed previously.
        """

        if not self._file_loaded:
            self._read()

        if self._previous_targets is None:
            return {}

        return self._previous_targets

    def _read(self):
        if os.path.exists(self._filename):
            with open(self._filename, 'r') as update_file:
                data = json.load(update_file)

            self._from_revision = int(data['version'])
            self._previous_targets = data['targets']

        self._file_loaded = True

    def set_end(self, end_revision, previous_targets):
        """
        Store the new current state of the data retrieval. `end_revision` is
        the latest revision that was parsed in this run, or `None` if no
        revisions were parsed. `previous_targets` is a dictionary of metric
        targets to compare against for checking if the next update has changes.
        """

        if end_revision is not None:
            data = {
                'version': end_revision,
                'targets': previous_targets
            }
            with open(self._filename, 'w') as update_file:
                json.dump(data, update_file)

def parse_svn_revision(rev):
    """
    Convert a Subversion revision number to an integer. Removes the leading 'r'
    if it is present.
    """

    if rev.startswith('r'):
        rev = rev[1:]

    return int(rev)

def parse_args():
    """
    Parse command line arguments.
    """

    description = "Obtain quality metric project definition and output JSON"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("project", help="project key")
    parser.add_argument("--repo", default="kwaliteitsmetingen/trunk",
                        help="Subversion directory with project definitions")
    parser.add_argument("--context", type=int, default=3,
                        help="Number of context lines for parser problems")
    parser.add_argument("--from-revision", type=parse_svn_revision,
                        dest="from_revision", default=None,
                        help="revision to start from gathering definitions")
    parser.add_argument("--to-revision", type=parse_svn_revision,
                        dest="to_revision", default=None,
                        help="revision to stop gathering definitions at")

    return parser.parse_args()

def process(project_key, project_name, args):
    """
    Perform the revision traversal and project definition parsing.
    """

    update_tracker = Update_Tracker(project_key)
    from_revision = update_tracker.get_start_revision(args.from_revision)

    repo = Subversion_Repository(args.repo)
    filename = project_name + '/project_definition.py'
    versions = repo.get_versions(filename, from_revision=from_revision,
                                 to_revision=args.to_revision, descending=False)

    diff = Metric_Difference(project_key, update_tracker.get_previous_targets())
    end_revision = None
    for version in versions:
        parser = Project_Definition_Parser(context_lines=args.context,
                                           file_time=version['commit_date'])
        contents = repo.get_contents(filename, revision=version['revision'])
        try:
            parser.load_definition(contents)
            metric_targets = parser.parse()
        except RuntimeError as error:
            print "Problem with revision {}: {}".format(version['revision'], error.message)
            continue

        diff.add_version(version, metric_targets)
        end_revision = version['revision']

    diff.export()

    update_tracker.set_end(end_revision, diff.previous_metric_targets)
    print '{} revisions parsed'.format(len(versions))

def main():
    """
    Main entry point.
    """

    config = ConfigParser.RawConfigParser()
    config.read("settings.cfg")
    args = parse_args()

    project_key = args.project
    if config.has_option('projects', project_key):
        project_name = config.get('projects', project_key)
    else:
        print 'No quality metrics options available for {}, skipping.'.format(project_key)
        return

    process(project_key, project_name, args)

if __name__ == "__main__":
    main()
