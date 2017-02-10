"""
Module for parsing project definitions.

Project definitions are Python scripts that define a number of domain objects,
such as projects, products and teams. Additionally, they specify options for
quality metrics, namely custom targets.
"""

import inspect
import os
import sys
import traceback
# Non-standard imports
import mock
from hqlib import domain, metric

__all__ = ["Project_Definition_Parser"]

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
            with mock.patch(self.__class__.__module__ + '.open', open_mock):
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
