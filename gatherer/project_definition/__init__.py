"""
Module for parsing project definitions.

Project definitions are Python scripts that define a number of domain objects,
such as projects, products and teams. Additionally, they specify options for
quality metrics, namely custom targets.
"""

import datetime
import importlib
import inspect
import os
import sys
import traceback
# Non-standard imports
import mock
from hqlib import domain, metric, metric_source

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
        try:
            replacement.configure_mock(name=name)
        except AttributeError:
            pass

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
    _previous_modules = {
        "ictu": ["isd"],
        "hqlib": ["quality_report", "qualitylib", "python.qualitylib"]
    }

    def __init__(self, context_lines=3, file_time=None):
        self.context_lines = context_lines

        if file_time is None:
            self.file_time = datetime.datetime.now()
        else:
            self.file_time = file_time

        self.data = {}

        self.domain_objects = self.get_mock_domain_objects(domain, self.DOMAIN)

    @staticmethod
    def filter_member(member, module_name):
        """
        Check whether a given member of a module is within the domain of objects
        that we need to mock or replace to be able to read the project
        definition.
        """

        if inspect.isclass(member) and member.__module__.startswith(module_name):
            return True

        return False

    def get_mock_domain_objects(self, module, module_name):
        """
        Create a dictionary of class names and their mocks and replacements.

        These classes live within a quality reporting module, such as domain
        or metric_source.
        """

        domain_objects = {}
        module_filter = lambda member: self.filter_member(member, module_name)
        for name, member in inspect.getmembers(module, module_filter):
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

    def get_compatibility_modules(self, module_path, value):
        """
        Create a dictionary of a module name extracted from the `module_path`
        stirng of (sub)modules and a given `value`. The dictionary also contains
        names of previous versions for the root module.
        """

        module_parts = module_path.split('.')
        root_name = module_parts.pop(0)
        root_names = [root_name]
        if root_name in self._previous_modules:
            root_names.extend(self._previous_modules[root_name])

        modules = {}
        for root in root_names:
            path = '.'.join([root] + module_parts)
            modules[path] = value

        return modules

    def get_hqlib_submodules(self):
        """
        Retrieve the submodule mocks that are directly imported from hqlib.

        These mocks can define additional behavior for keeping track of data.
        """

        raise NotImplementedError("Must be extended by subclass")

    def get_mock_modules(self):
        """
        Get mock objects for all module imports done by project definitions
        to be able to safely read it.
        """

        hqlib = mock.MagicMock(**self.get_hqlib_submodules())
        hqlib_domain = mock.MagicMock(**self.domain_objects)

        # Mock the internal source module (ictu, backwards compatible: isd) and
        # the reporting module (hqlib, backwards compatible: quality_report,
        # qualitylib) as well as the submodules that the project definition
        # imports.
        modules = {}
        modules.update(self.get_compatibility_modules('hqlib', hqlib))
        modules.update(self.get_compatibility_modules('hqlib.domain',
                                                      hqlib_domain))

        return modules

    def load_definition(self, contents):
        """
        Safely read the contents of a project definition file.

        This uses patching and mocks to avoid loading external repositories
        through the quality reporting framework and to skip internal information
        that we do not need.
        """

        modules = self.get_mock_modules()

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
            if self.filter_domain_object(mock_object):
                for call in mock_object.call_args_list:
                    self.parse_domain_call(*call)

        return self.data

    def filter_domain_object(self, mock_object):
        """
        Filter a given domain object `mock_object` to check whether we want to
        extract data from its initialization call.
        """

        raise NotImplementedError("Must be extended by subclass")

    def parse_domain_call(self, args, keywords):
        """
        Extract data from the domain object initialization call from within the
        project definition.
        """

        raise NotImplementedError("Must be extened by subclasses")

    @staticmethod
    def get_class_name(class_type):
        """
        Retrieve the class name for a class type variable.

        This function handles mock objects by retrieving the appropriate name
        from it.
        """

        if isinstance(class_type, mock.Mock):
            class_name = class_type.name
            if isinstance(class_name, mock.Mock):
                # pylint: disable=protected-access
                class_name = class_type._mock_name
        else:
            class_name = class_type.__name__

        return class_name

class Sources_Parser(Project_Definition_Parser):
    """
    A project definition parser that extracts source URLs for the products
    specified in the definition.
    """

    METRIC_SOURCE = 'hqlib.metric_source'

    def __init__(self, path, **kwargs):
        super(Sources_Parser, self).__init__(**kwargs)

        self.sys_path = path
        self.source_objects = self.get_mock_domain_objects(metric_source,
                                                           self.METRIC_SOURCE)

    def get_hqlib_submodules(self):
        return {
            'metric_source': mock.MagicMock(**metric_source.__dict__)
        }

    def get_mock_modules(self):
        modules = super(Sources_Parser, self).get_mock_modules()

        try:
            modules['ictu'] = importlib.import_module('ictu')
            modules['ictu.convention'] = importlib.import_module('ictu.convention')
            modules['ictu.metric_source'] = importlib.import_module('ictu.metric_source')
        except:
            raise

        hqlib_metric_source = mock.MagicMock(**self.source_objects)
        modules.update(self.get_compatibility_modules(self.METRIC_SOURCE,
                                                      hqlib_metric_source))

        return modules

    def load_definition(self, content):
        with mock.patch('sys.path', sys.path + [self.sys_path]):
            super(Sources_Parser, self).load_definition(content)

    def filter_domain_object(self, mock_object):
        return isinstance(mock_object, (domain.Product, domain.Application, domain.Component))

    def parse_domain_call(self, args, keywords):
        if "name" in keywords:
            name = keywords["name"]
        else:
            name = args[1]

        if "metric_source_ids" not in keywords:
            return

        sources = {}
        for key, value in keywords["metric_source_ids"].items():
            if isinstance(key, (metric_source.Git, metric_source.Subversion)):
                class_name = self.get_class_name(type(key))
                source_url = key.url()
                if source_url is None:
                    source_url = value

                sources[class_name] = source_url

        if sources:
            self.data[name] = sources

class Metric_Options_Parser(Project_Definition_Parser):
    """
    A project definition parser that extracts metric options from the domain
    objects specified in the definition.
    """

    _old_metric_options = {
        'low_targets': 'low_target',
        'targets': 'target',
        'technical_debt_targets': 'debt_target'
    }

    def filter_domain_object(self, mock_object):
        return isinstance(mock_object, domain.DomainObject)

    def get_hqlib_submodules(self):
        return {
            "metric": mock.MagicMock(**metric.__dict__)
        }

    def get_mock_modules(self):
        modules = super(Metric_Options_Parser, self).get_mock_modules()

        ictu = mock.MagicMock()
        ictu_convention = mock.MagicMock()
        ictu_metric_source = mock.MagicMock()

        modules.update(self.get_compatibility_modules('ictu', ictu))
        modules.update(self.get_compatibility_modules('ictu.convention',
                                                      ictu_convention))
        modules.update(self.get_compatibility_modules('ictu.metric_source',
                                                      ictu_metric_source))

        return modules

    def parse_domain_call(self, args, keywords):
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

        for old_keyword, new_key in self._old_metric_options.iteritems():
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

        class_name = self.get_class_name(metric_type)

        metric_name = class_name + name
        if metric_name in self.data:
            targets = self.data[metric_name]
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

        self.data[metric_name] = targets

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
