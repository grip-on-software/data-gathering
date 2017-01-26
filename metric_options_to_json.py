import argparse
import ConfigParser
import datetime
import dateutil.tz
import inspect
import json
import mock
import os.path
import sys
import svn.local
import traceback
from hqlib import domain, metric

replacements = {}

# Define some classes that are backward compatible with earlier versions of 
# hqlib (quality_report, qualitylib). This suppresses argument exceptions.
def replaces(target):
    def decorator(subject):
        replacements[target] = subject
        return subject

    return decorator

@replaces(domain.TechnicalDebtTarget)
class TechnicalDebtTarget(domain.TechnicalDebtTarget):
    def __init__(self, target_value, explanation='', unit=''):
        super(TechnicalDebtTarget, self).__init__(target_value, explanation)

@replaces(domain.DynamicTechnicalDebtTarget)
class DynamicTechnicalDebtTarget(domain.DynamicTechnicalDebtTarget):
    def __init__(self, initial_target_value, initial_datetime, end_target_value, end_datetime, explanation='', unit=''):
        super(DynamicTechnicalDebtTarget, self).__init__(initial_target_value, initial_datetime, end_target_value, end_datetime, explanation)

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
            if member in replacements:
                domain_objects[name] = replacements[member]
            else:
                domain_objects[name] = mock.Mock(name=name, spec_set=member)

        return domain_objects

    def format_exception(self, contents, emulate_context=True):
        etype, value, tb = sys.exc_info()
        formatted_lines = traceback.format_exception_only(etype, value)
        message = "Could not parse project definition: " + formatted_lines[-1]
        if self.context_lines >= 0:
            message += ''.join(formatted_lines[:-1])
            if emulate_context:
                line = traceback.extract_tb(tb)[-1][1]
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
        domain = mock.MagicMock(**self.domain_objects)

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
            'hqlib.domain': domain,
            'quality_report': hqlib,
            'quality_report.domain': domain,
            'qualitylib': hqlib,
            'qualitylib.domain': domain
        }
        open_mock = mock.mock_open()

        with mock.patch.dict('sys.modules', modules):
            with mock.patch('__main__.open', open_mock):
                try:
                    # Load the project definition by executing the contents of 
                    # the file with altered module definitions.
                    exec(contents)
                except SyntaxError as e:
                    # Most syntax errors have correct line marker information
                    if e.text is None:
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
                    args, kwargs = call
                    self.parse_domain_call(kwargs)

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
            for metric, options in keywords["metric_options"].iteritems():
                self.parse_metric(name, metric, options=options)

        for old_keyword, new_key in self.old_metric_options.iteritems():
            if old_keyword in keywords:
                for metric, option in keywords[old_keyword].iteritems():
                    self.parse_metric(name, metric, options={new_key: option},
                        options_type='old_options'
                    )

    def parse_metric(self, name, metric, options, options_type='metric_options'):
        """
        Update the metric targets for a metric specified in the project
        definition.
        """

        if isinstance(metric, mock.Mock):
            class_name = metric._mock_name
        else:
            class_name = metric.__name__
            
        metric_name = class_name + name
        if metric_name in self.metric_targets:
            targets = self.metric_targets[metric_name]
        elif isinstance(metric, mock.Mock):
            # No default data available
            targets = {
                'low_target': '0',
                'target': '0',
                'type': 'old_options',
                'comment': ''
            }
        else:
            targets = {
                'low_target': str(int(metric.low_target_value)),
                'target': str(int(metric.target_value)),
                'type': options_type,
                'comment': ''
            }

        for key in ('low_target', 'target', 'comment'):
            if key in options:
                targets[key] = str(options[key])

        targets.update(self.parse_debt_target(options))

        self.metric_targets[metric_name] = targets

    def parse_debt_target(self, options):
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
    def __init__(self, path='.'):
        self.path = os.path.expanduser(path)
        self.svn = svn.local.LocalClient(self.path)

    def get_versions(self, filename, from_revision=None, to_revision=None, descending=False):
        versions = []
        log = self.svn.log_default(rel_filepath=filename,
            revision_from=from_revision, revision_to=to_revision)
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
            reverse=descending
        )

    def get_contents(self, filename, revision=None):
        return self.svn.cat(filename, revision=revision)

class Metric_Difference(object):
    """
    Class that determines whether metric options were changed.
    """

    def __init__(self, previous_targets=None):
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

    @property
    def previous_metric_targets(self):
        return self._previous_metric_targets

    @property
    def unique_versions(self):
        return self._unique_versions

    @property
    def unique_metric_targets(self):
        return self._unique_metric_targets

class Update_Tracker(object):
    def __init__(self, project_key):
        self._project_key = project_key
        self._filename = self._project_key + '/metric_options_update.json'

        self._file_loaded = False
        self._from_revision = None
        self._previous_targets = None

    def get_start_revision(self, from_revision=None):
        if from_revision is not None:
            return from_revision

        if not self._file_loaded:
            self._read()

        if self._from_revision is None:
            return None

        return self._from_revision + 1

    def get_previous_targets(self):
        if not self._file_loaded:
            self._read()

        if self._previous_targets is None:
            return {}

        return self._previous_targets

    def _read(self):
        if os.path.exists(self._filename):
            with open(self._filename, 'r') as f:
                data = json.load(f)

            self._from_revision = int(data['version'])
            self._previous_targets = data['targets']

        self._file_loaded = True

    def set_end(self, end_revision, previous_targets):
        if end_revision is not None:
            data = {
                'version': end_revision,
                'targets': previous_targets
            }
            with open(self._filename, 'w') as f:
                json.dump(data, f)

def parse_svn_revision(rev):
    if rev.startswith('r'):
        rev = rev[1:]

    return int(rev)

def parse_args():
    parser = argparse.ArgumentParser(description="Obtain quality metric project definition data and convert to JSON format readable by the database importer.")
    parser.add_argument("project", help="project key")
    parser.add_argument("--repo", default="kwaliteitsmetingen/trunk", help="Subversion repository containing the project definitions (checked out at trunk)")
    parser.add_argument("--context", type=int, default=3, help="Number of lines of context to show for problematic definitions")
    parser.add_argument("--from-revision", type=parse_svn_revision, dest="from_revision", default=None, help="revision to start from gathering historical definitions")
    parser.add_argument("--to-revision", type=parse_svn_revision, dest="to_revision", default=None, help="revision to stop gathering historical definitions at")

    return parser.parse_args()

def main():
    config = ConfigParser.RawConfigParser()
    config.read("settings.cfg")
    args = parse_args()

    project_key = args.project
    if config.has_option('projects', project_key):
        project_name = config.get('projects', project_key)
    else:
        print('No quality metrics options available for ' + project_key + ', skipping.')
        return

    update_tracker = Update_Tracker(project_key)
    from_revision = update_tracker.get_start_revision(args.from_revision)

    svn = Subversion_Repository(args.repo)
    filename = project_name + '/project_definition.py'
    versions = svn.get_versions(filename, from_revision=from_revision,
        to_revision=args.to_revision, descending=False
    )

    diff = Metric_Difference(update_tracker.get_previous_targets())
    end_revision = None
    for version in versions:
        parser = Project_Definition_Parser(context_lines=args.context,
            file_time=version['commit_date']
        )
        contents = svn.get_contents(filename, revision=version['revision'])
        try:
            parser.load_definition(contents)
            metric_targets = parser.parse()
        except RuntimeError as e:
            print("Problem with revision {}: {}".format(version['revision'], e.message))
            continue

        diff.add_version(version, metric_targets)
        end_revision = version['revision']

    with open(project_key + '/data_metric_versions.json', 'w') as outfile:
        json.dump(diff.unique_versions, outfile, indent=4)

    with open(project_key + '/data_metric_targets.json', 'w') as outfile:
        json.dump(diff.unique_metric_targets, outfile, indent=4)

    update_tracker.set_end(end_revision, diff.previous_metric_targets)
    print('{} revisions parsed'.format(len(versions)))

if __name__ == "__main__":
    main()
