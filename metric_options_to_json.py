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
        message = "Could not parse project definition: " + traceback.format_exc()
        if emulate_context:
            tb = sys.exc_traceback
            line = traceback.extract_tb(tb)[-1][1]
            lines = contents.split('\n')
            range_start = max(0, line-self.context_lines-1)
            range_end = min(len(lines), line+self.context_lines)
            message += "Context:\n" + '\n'.join(lines[range_start:range_end])

        raise RuntimeError(message)

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

        with mock.patch.dict('sys.modules', modules):
            try:
                # Load the project definition by executing the contents of the 
                # file with altered module definitions.
                exec(contents)
            except SyntaxError as e:
                # Most syntax errors have correct line marker information
                if e.text is None:
                    self.format_exception(contents)
                else:
                    self.format_exception(contents, emulate_context=False)
            except Exception:
                # Because of string execution, the line number of the exception 
                # becomes incorrect. Attempt to emulate the context display 
                # using traceback extraction.
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
                'low_target': '',
                'target': '',
                'type': 'old_options',
                'comment': ''
            }
        else:
            targets = {
                'low_target': str(metric.low_target_value),
                'target': str(metric.target_value),
                'type': options_type,
                'comment': ''
            }

        for key in ('low_target', 'target', 'comment'):
            if key in options:
                targets[key] = str(options[key])

        if 'debt_target' in options:
            debt = options['debt_target']

            datetime_args = {'now.return_value': self.file_time} 
            with mock.patch('datetime.datetime', **datetime_args):
                debt_target = debt.target_value()
                debt_comment = debt.explanation()

                targets['target'] = str(debt_target)
                targets['type'] = debt.__class__.__name__
                targets['comment'] = debt_comment

        self.metric_targets[metric_name] = targets

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
            version = {
                'revision': entry.revision,
                'developer': entry.author,
                'message': entry.msg,
                'commit_date': datetime.datetime.strftime(commit_date, '%Y-%m-%d %H:%M:%S')
            }

            versions.append(version)

        return sorted(versions, key=lambda version: version['revision'],
            reverse=descending
        )

    def get_contents(self, filename, revision=None):
        return self.svn.cat(filename, revision=revision)

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
    # TODO: Add incremental updates (track latest revision and use it as 
    # from-revision by default)
    config = ConfigParser.RawConfigParser()
    config.read("settings.cfg")
    args = parse_args()

    project_key = args.project
    if config.has_option('projects', project_key):
        project_name = config.get('projects', project_key)
    else:
        print('No quality metrics options available for ' + project_key + ', skipping.')
        return

    svn = Subversion_Repository(args.repo)
    filename = project_name + '/project_definition.py'
    versions = svn.get_versions(filename, from_revision=args.from_revision,
        to_revision=args.to_revision, descending=False
    )
    previous_metric_targets = {}

    unique_versions = []
    unique_metric_targets = []
    for version in versions:
        parser = Project_Definition_Parser(file_time=version['commit_date'])
        contents = svn.get_contents(filename, revision=version['revision'])
        try:
            parser.load_definition(contents)
            metric_targets = parser.parse()
        except RuntimeError as e:
            print("Problem with revision {}: {}".format(version['revision'], e))
            continue

        # Detect whether the metrics and definitions have changed
        if metric_targets != previous_metric_targets:
            unique_versions.append(version)
            for name, metric_target in metric_targets.iteritems():
                if name in previous_metric_targets:
                    previous_metric_target = previous_metric_targets[name]
                else:
                    previous_metric_target = {}

                if metric_target != previous_metric_targets:
                    unique_target = dict(metric_target)
                    unique_target['name'] = name
                    unique_target['revision'] = version['revision']
                    unique_metric_targets.append(unique_target)

            previous_metric_targets = metric_targets

    with open(project_key + '/data_metric_versions.json', 'w') as outfile:
        json.dump(unique_versions, outfile, indent=4)

    with open(project_key + '/data_metric_targets.json', 'w') as outfile:
        json.dump(unique_metric_targets, outfile, indent=4)

if __name__ == "__main__":
    main()