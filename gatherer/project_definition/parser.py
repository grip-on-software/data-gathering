"""
Module for parsing project definitions.

Project definitions are Python scripts that define a number of domain objects,
such as projects, products and teams. Additionally, they specify options for
quality metrics, namely custom targets.
"""

from builtins import str, object
from past.builtins import basestring
import datetime
import importlib
import inspect
import logging
import sys
import traceback
# Non-standard imports
import mock
from hqlib import domain, metric, metric_source
from .compatibility import Compatibility, COMPACT_HISTORY
from ..utils import get_datetime, parse_unicode

__all__ = ["Project_Definition_Parser"]

class Project_Definition_Parser(object):
    """
    Parser for project definitions of the quality reporting tool.
    """

    DOMAIN = 'hqlib.domain'
    _previous_modules = {
        "ictu": ["isd"],
        "hqlib": ["quality_report", "qualitylib", "python.qualitylib"],
        "hqlib.domain": ["qualitylib.ecosystem"]
    }

    def __init__(self, context_lines=3, file_time=None):
        self.context_lines = context_lines

        if file_time is None:
            self.file_time = datetime.datetime.now()
        else:
            self.file_time = get_datetime(file_time, '%Y-%m-%d %H:%M:%S')

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
        Wrap a problem that is encountered while parsing the project definition
        `contents`. This method must be called from an exception context.
        Its returned value is a `RuntimeError` object, which must be raised
        from that context.
        """

        etype, value, trace = sys.exc_info()
        formatted_lines = traceback.format_exception_only(etype, value)
        message = "Could not parse project definition: " + formatted_lines[-1]
        if self.context_lines >= 0:
            message += ''.join(formatted_lines[:-1])
            if emulate_context:
                line = traceback.extract_tb(trace)[-1][1]
                if isinstance(contents, bytes):
                    contents = contents.decode('utf-8')
                lines = contents.split('\n')
                range_start = max(0, line-self.context_lines-1)
                range_end = min(len(lines), line+self.context_lines)
                message += "Context:\n" + '\n'.join(lines[range_start:range_end])

        return RuntimeError(message.strip())

    def _format_compatibility_modules(self, root_name, module_parts):
        root_names = [root_name]
        if root_name in self._previous_modules:
            root_names.extend(self._previous_modules[root_name])

        for root in root_names:
            yield '.'.join([root] + module_parts)

    def get_compatibility_modules(self, module_path, value):
        """
        Create a dictionary of a module name extracted from the `module_path`
        stirng of (sub)modules and a given `value`. The dictionary also contains
        names of previous versions for the root module.
        """

        modules = {}
        module_parts = module_path.split('.')
        root_name = None
        for index, part in enumerate(module_parts):
            if index == 0:
                root_name = part
            else:
                root_name = '{}.{}'.format(root_name, part)

            parts = module_parts[index+1:]
            module_names = self._format_compatibility_modules(root_name, parts)

            # Fill the dictiornary of (compatibility) module names and the
            # implementation module.
            for path in module_names:
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

    def load_definition(self, filename, contents):
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
                # pylint: disable=exec-used
                try:
                    env = {'__file__': filename, 'open': open_mock}
                    exec(contents, env, env)
                except SyntaxError as exception:
                    # Most syntax errors have correct line marker information
                    if exception.text is None:
                        raise self.format_exception(contents)
                    else:
                        raise self.format_exception(contents,
                                                    emulate_context=False)
                except Exception:
                    # Because of string execution, the line number of the
                    # exception becomes incorrect. Attempt to emulate the
                    # context display using traceback extraction.
                    raise self.format_exception(contents)

    def parse(self):
        """
        Retrieve metric targets from the collected domain objects that were
        specified in the project definition.
        """

        for mock_object in list(self.domain_objects.values()):
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
        Retrieve the class name for a class type variable or object.

        This function handles mock objects by retrieving the appropriate name
        from it.
        """

        if isinstance(class_type, mock.Mock):
            class_name = class_type.name
            if isinstance(class_name, mock.Mock):
                # pylint: disable=protected-access
                class_name = class_type._mock_name
        else:
            if not isinstance(class_type, type):
                class_type = class_type.__class__

            class_name = class_type.__name__

        return class_name

class Project_Parser(Project_Definition_Parser):
    """
    A project definition parser that retrieves the project name.
    """

    def get_hqlib_submodules(self):
        return {}

    def get_mock_modules(self):
        modules = super(Project_Parser, self).get_mock_modules()

        ictu = mock.MagicMock()
        ictu_convention = mock.MagicMock()
        ictu_metric_source = mock.MagicMock()

        modules.update(self.get_compatibility_modules('ictu', ictu))
        modules.update(self.get_compatibility_modules('ictu.convention',
                                                      ictu_convention))
        modules.update(self.get_compatibility_modules('ictu.metric_source',
                                                      ictu_metric_source))

        return modules

    def filter_domain_object(self, mock_object):
        return isinstance(mock_object, domain.Project)

    def parse_domain_call(self, args, keywords):
        if "name" in keywords:
            name = keywords["name"]
        elif len(args) > 1:
            name = args[1]
        else:
            return

        self.data['quality_display_name'] = name

class Sources_Parser(Project_Definition_Parser):
    """
    A project definition parser that extracts source URLs for the products
    specified in the definition.
    """

    METRIC_SOURCE = 'hqlib.metric_source'
    DOMAIN_CLASSES = (
        domain.Application, domain.Component, domain.Environment,
        domain.Product, domain.Project
    )
    SOURCE_CLASSES = {
        'History': metric_source.History,
        'CompactHistory': COMPACT_HISTORY,
        'Jenkins': metric_source.Jenkins,
        'Jira': metric_source.Jira,
        'Git': metric_source.Git,
        'Subversion': metric_source.Subversion
    }

    def __init__(self, path, **kwargs):
        super(Sources_Parser, self).__init__(**kwargs)

        self.sys_path = path
        self.source_objects = self.get_mock_domain_objects(metric_source,
                                                           self.METRIC_SOURCE)
        self.source_objects.update(self.SOURCE_CLASSES)
        self.source_types = tuple(self.SOURCE_CLASSES.values())

    def get_hqlib_submodules(self):
        return {
            'metric_source': mock.MagicMock(**self.source_objects)
        }

    def get_mock_modules(self):
        modules = super(Sources_Parser, self).get_mock_modules()

        hqlib_metric_source = mock.MagicMock(**self.source_objects)
        modules.update(self.get_compatibility_modules(self.METRIC_SOURCE,
                                                      hqlib_metric_source))

        with mock.patch.dict('sys.modules', modules):
            ictu = importlib.import_module('ictu')
            ictu.person = mock.MagicMock()
            ictu_metric_source = importlib.import_module('ictu.metric_source')
            ictu_convention = importlib.import_module('ictu.convention')
            ictu.metric_source = ictu_metric_source
            modules.update(self.get_compatibility_modules('ictu', ictu))
            modules.update(self.get_compatibility_modules('ictu.convention',
                                                          ictu_convention))
            modules.update(self.get_compatibility_modules('ictu.metric_source',
                                                          ictu_metric_source))

        return modules

    def load_definition(self, filename, contents):
        with mock.patch('sys.path', sys.path + [self.sys_path]):
            super(Sources_Parser, self).load_definition(filename, contents)

    def filter_domain_object(self, mock_object):
        return isinstance(mock_object, self.DOMAIN_CLASSES)

    def parse_domain_call(self, args, keywords):
        if "name" in keywords:
            name = keywords["name"]
        elif len(args) > 1:
            name = args[1]
        else:
            # Likely a call to a superclass constructor
            return

        logging.debug('Name: %s', name)

        self._parse_sources(name, keywords, "metric_source_ids", from_key=True)
        self._parse_sources(name, keywords, "metric_sources", from_key=False)

    def _parse_sources(self, name, keywords, keyword, from_key=True):
        if keyword not in keywords:
            return

        if not isinstance(keywords[keyword], dict):
            logging.debug('keyword %s does not hold a dict', keyword)
            return

        sources = {}
        for key, items in list(keywords[keyword].items()):
            if not isinstance(items, (list, tuple)):
                items = [items]

            for value in items:
                class_name, source_value = self._parse_source_value(key, value,
                                                                    from_key)

                if class_name is not None:
                    sources.setdefault(class_name, set())
                    sources[class_name].add(source_value)

        if sources:
            self.data[name] = sources

    def _parse_source_value(self, key, value, from_key):
        if from_key and isinstance(key, self.source_types):
            class_name = self.get_class_name(type(key))
            source_url = key.url()
            if source_url is None or value.startswith(source_url):
                source_url = value

            return class_name, source_url
        elif not from_key and isinstance(value, self.source_types):
            class_name = self.get_class_name(value)
            logging.debug('Class name: %s', class_name)
            if isinstance(value, mock.MagicMock):
                source_value = value.call_args_list[0][0][0]
            else:
                source_value = value.url()

            if source_value is not None:
                return class_name, source_value

        return None, None

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
            for metric_type, options in keywords["metric_options"].items():
                self.parse_metric(name, metric_type, options=options)

        for old_keyword, new_key in self._old_metric_options.items():
            if old_keyword in keywords:
                for metric_type, option in keywords[old_keyword].items():
                    self.parse_metric(name, metric_type,
                                      options={new_key: option},
                                      options_type='old_options')

    def parse_metric(self, name, metric_type, options=None,
                     options_type='metric_options'):
        """
        Update the metric targets for a metric specified in the project
        definition.
        """

        # Ensure that the metric type is a class and the options of a metric
        # target is a dictionary.
        if not inspect.isclass(metric_type):
            return
        if not isinstance(options, dict):
            return

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
            try:
                targets = {
                    'low_target': str(int(metric_type.low_target_value)),
                    'target': str(int(metric_type.target_value)),
                    'type': options_type,
                    'comment': ''
                }
            except (ValueError, AttributeError):
                # Could not parse targets as integers
                return

        for key in ('low_target', 'target', 'comment'):
            if key in options:
                if isinstance(options[key], basestring):
                    targets[key] = parse_unicode(options[key])
                else:
                    targets[key] = str(options[key])

        targets.update(self.parse_debt_target(options))
        targets.update({
            'base_name': class_name,
            'domain_name': name
        })

        self.data[metric_name] = targets

    def parse_debt_target(self, options):
        """
        Retrieve data regarding a technical debt target.
        """

        if 'debt_target' in options:
            debt = options['debt_target']
            if not isinstance(debt, domain.TechnicalDebtTarget):
                return {}

            datetime_args = {'now.return_value': self.file_time}
            with mock.patch('datetime.datetime', **datetime_args):
                try:
                    debt_target = debt.target_value()
                except TypeError:
                    # Dynamic technical debt target may have incomparable
                    # values for start/end dates.
                    return {}

                debt_comment = debt.explanation()

                return {
                    'target': str(debt_target),
                    'type': debt.__class__.__name__,
                    'comment': debt_comment
                }

        return {}
