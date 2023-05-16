"""
Module for parsing project definitions.

Project definitions are Python scripts that define a number of domain objects,
such as projects, products and teams. Additionally, they specify options for
quality metrics, namely custom targets.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University
Copyright 2017-2023 Leon Helwerda

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import datetime
from distutils.version import LooseVersion
import importlib
import inspect
import logging
import sys
import traceback
from types import ModuleType
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, \
    Set, Tuple, Type, Union
from unittest.mock import Mock, MagicMock, mock_open, patch
# Non-standard imports
from hqlib import domain, metric, metric_source
from hqlib.utils import version_number_to_numerical
from .base import SourceUrl, Definition_Parser
from .compatibility import Compatibility, COMPACT_HISTORY, JIRA, JIRA_FILTER, \
    SONAR, DomainType
from ..utils import get_datetime, parse_unicode

__all__ = ["Project_Definition_Parser"]

SourceID = Union[Type[domain.DomainObject], domain.DomainObject]

class Project_Definition_Parser(Definition_Parser):
    """
    Parser for project definitions of the quality reporting tool.
    """

    DOMAIN = 'hqlib.domain'
    _previous_modules = {
        "ictu": ["isd"],
        "hqlib": ["quality_report", "qualitylib", "python.qualitylib"],
        "hqlib.domain": ["qualitylib.ecosystem"]
    }

    def __init__(self, context_lines: int = 3,
                 file_time: Optional[str] = None, **options: Any) -> None:
        super().__init__(**options)
        self.context_lines = context_lines

        if file_time is None:
            self.file_time = datetime.datetime.now()
        else:
            self.file_time = get_datetime(file_time, '%Y-%m-%d %H:%M:%S')

        self.data: Dict[str, Any] = {}

        self.domain_objects = self.get_mock_domain_objects(domain, self.DOMAIN)

    @staticmethod
    def filter_member(member: Any, module_name: str) -> bool:
        """
        Check whether a given member of a module is within the domain of objects
        that we need to mock or replace to be able to read the project
        definition.
        """

        if inspect.isclass(member) and member.__module__.startswith(module_name):
            return True

        return False

    def get_mock_domain_objects(self, module: ModuleType, module_name: str) \
            -> Dict[str, Mock]:
        """
        Create a dictionary of class names and their mocks and replacements.

        These classes live within a quality reporting module, such as domain
        or metric_source.
        """

        domain_objects: Dict[str, Mock] = {}
        module_filter = lambda member: self.filter_member(member, module_name)
        for name, member in inspect.getmembers(module, module_filter):
            replacement = Compatibility.get_replacement(name, member)
            if isinstance(replacement, Mock):
                domain_objects[name] = replacement

        return domain_objects

    def format_exception(self, contents: Union[str, bytes],
                         emulate_context: bool = True) -> RuntimeError:
        """
        Wrap a problem that is encountered while parsing the project definition
        `contents`. This method must be called from an exception context.
        Its returned value is a `RuntimeError` object, which must be raised
        from that context.
        """

        etype, value, trace = sys.exc_info()
        formatted_lines = traceback.format_exception_only(etype, value)
        message = f"Could not parse project definition: {formatted_lines[-1]}"
        if self.context_lines >= 0:
            message = f'{message}{"".join(formatted_lines[:-1])}'
            if emulate_context:
                line = traceback.extract_tb(trace)[-1].lineno
                if line is None:
                    line = 0
                if isinstance(contents, bytes):
                    text = contents.decode('utf-8')
                else:
                    text = contents
                lines = text.split('\n')
                range_start = max(0, line - self.context_lines - 1)
                range_end = min(len(lines), line + self.context_lines)
                context = '\n'.join(lines[range_start:range_end])
                message = f"{message}Context:\n{context}"

        return RuntimeError(message.strip())

    def _format_compatibility_modules(self, root_name: str,
                                      module_parts: List[str]) -> Iterator[str]:
        root_names = [root_name]
        if root_name in self._previous_modules:
            root_names.extend(self._previous_modules[root_name])

        for root in root_names:
            yield '.'.join([root] + module_parts)

    def get_compatibility_modules(self, module_path: str, value: ModuleType) \
            -> Dict[str, ModuleType]:
        """
        Create a dictionary of a module name extracted from the `module_path`
        string of (sub)modules and a given `value`. The dictionary also contains
        names of previous versions for the root module.
        """

        modules: Dict[str, ModuleType] = {}
        module_parts = module_path.split('.')
        root_name = None
        for index, part in enumerate(module_parts):
            if index == 0:
                root_name = part
            else:
                root_name = f'{root_name}.{part}'

            parts = module_parts[index+1:]
            module_names = self._format_compatibility_modules(root_name, parts)

            # Fill the dictiornary of (compatibility) module names and the
            # implementation module.
            for path in module_names:
                modules[path] = value

        return modules

    def get_hqlib_submodules(self) -> Dict[str, Mock]:
        """
        Retrieve the submodule mocks that are directly imported from hqlib.

        These mocks can define additional behavior for keeping track of data.
        """

        raise NotImplementedError("Must be extended by subclass")

    def get_mock_modules(self) -> Dict[str, ModuleType]:
        """
        Get mock objects for all module imports done by project definitions
        to be able to safely read it.
        """

        hqlib = MagicMock(**self.get_hqlib_submodules())
        hqlib_domain = MagicMock(**self.domain_objects)

        # Mock the internal source module (ictu, backwards compatible: isd) and
        # the reporting module (hqlib, backwards compatible: quality_report,
        # qualitylib) as well as the submodules that the project definition
        # imports.
        modules: Dict[str, ModuleType] = {}
        modules.update(self.get_compatibility_modules('hqlib', hqlib))
        modules.update(self.get_compatibility_modules('hqlib.domain',
                                                      hqlib_domain))

        return modules

    def load_definition(self, filename: str, contents: Union[str, bytes]) -> None:
        """
        Safely read the contents of a project definition file.

        This uses patching and mocks to avoid loading external repositories
        through the quality reporting framework and to skip internal information
        that we do not need.
        """

        modules = self.get_mock_modules()

        open_mock = mock_open()

        with patch.dict('sys.modules', modules):
            with patch(f'{self.__class__.__module__}.open', open_mock):
                # Load the project definition by executing the contents of
                # the file with altered module definitions. This should be safe
                # since all relevant modules and context has been patched.
                # pylint: disable=exec-used
                try:
                    env = {
                        f'__{"file"}__': filename,
                        'open': open_mock
                    }
                    exec(contents, env, env)
                except SyntaxError as error:
                    # Most syntax errors have correct line marker information
                    if error.text is None:
                        raise self.format_exception(contents) from error
                    raise self.format_exception(contents,
                                                emulate_context=False) from error
                except Exception as error:
                    # Because of string execution, the line number of the
                    # exception becomes incorrect. Attempt to emulate the
                    # context display using traceback extraction.
                    raise self.format_exception(contents) from error

    def parse(self) -> Dict[str, Any]:
        """
        Retrieve metric targets from the collected domain objects that were
        specified in the project definition.
        """

        for mock_object in list(self.domain_objects.values()):
            if self.filter_domain_object(mock_object):
                for call in mock_object.call_args_list:
                    self.parse_domain_call(mock_object, *call)

        return self.data

    def filter_domain_object(self, mock_object: Mock) -> bool:
        """
        Filter a given domain object `mock_object` to check whether we want to
        extract data from its initialization call.
        """

        raise NotImplementedError("Must be extended by subclass")

    def parse_domain_call(self, mock_object: Mock, args: Sequence[Any],
                          keywords: Mapping[str, Any]) -> None:
        """
        Extract data from the domain object initialization call from within the
        project definition.
        """

        raise NotImplementedError("Must be extened by subclasses")

    @staticmethod
    def get_class_name(class_type: Union[Type, object]) -> str:
        """
        Retrieve the class name for a class type variable or object.

        This function handles mock objects by retrieving the appropriate name
        from it.
        """

        if isinstance(class_type, Mock): # type: ignore[misc]
            class_name = class_type.name
            if isinstance(class_name, Mock): # type: ignore[misc]
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

    def get_hqlib_submodules(self) -> Dict[str, Mock]:
        return {}

    def get_mock_modules(self) -> Dict[str, ModuleType]:
        modules = super().get_mock_modules()

        ictu = MagicMock()
        ictu_convention = MagicMock()
        ictu_metric_source = MagicMock()

        modules.update(self.get_compatibility_modules('ictu', ictu))
        modules.update(self.get_compatibility_modules('ictu.convention',
                                                      ictu_convention))
        modules.update(self.get_compatibility_modules('ictu.metric_source',
                                                      ictu_metric_source))

        return modules

    def filter_domain_object(self, mock_object: Mock) -> bool:
        return isinstance(mock_object, domain.Project)

    def parse_domain_call(self, mock_object: Mock, args: Sequence[Any],
                          keywords: Mapping[str, Any]) -> None:
        if "name" in keywords:
            name = str(keywords["name"])
        elif len(args) > 1:
            name = str(args[1])
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
        domain.Application, domain.Component, domain.Document,
        domain.Environment, domain.Product, domain.Project
    )
    SOURCE_CLASSES: Dict[str, Type[domain.DomainObject]] = {
        'History': metric_source.History,
        'CompactHistory': COMPACT_HISTORY,
        'Jenkins': metric_source.Jenkins,
        'Jira': JIRA,
        'JiraFilter': JIRA_FILTER,
        'Sonar': SONAR,
        'Git': metric_source.Git,
        'Subversion': metric_source.Subversion
    }
    SOURCES_MAP = {
        'Subversion': 'subversion',
        'Git': 'git',
        'History': 'history',
        'CompactHistory': 'compact-history',
        'Jenkins': 'jenkins',
        'Jira': 'jira',
        'JiraFilter': 'jira',
        'Sonar': 'sonar'
    }

    SOURCE_ID_SOURCES = ('Sonar', 'Git', 'Subversion')
    SOURCES_DOMAIN_FILTER = ['Document']

    DUMMY_URLS = (None, 'dummy', '.', '/')

    def __init__(self, path: str = ".", context_lines: int = 3,
                 file_time: Optional[str] = None) -> None:
        super().__init__(context_lines=context_lines, file_time=file_time)

        self.sys_path = path
        self.source_objects: Dict[str, Union[Mock, DomainType]] = {}
        mocks = self.get_mock_domain_objects(metric_source, self.METRIC_SOURCE)
        self.source_objects.update(mocks)
        self.source_objects.update(self.SOURCE_CLASSES)
        self.source_types: Tuple[Type[domain.DomainObject], ...] = \
            tuple(self.SOURCE_CLASSES.values())

    def get_hqlib_submodules(self) -> Dict[str, Mock]:
        return {
            'metric_source': MagicMock(**self.source_objects)
        }

    def get_mock_modules(self) -> Dict[str, ModuleType]:
        modules = super().get_mock_modules()

        hqlib_metric_source = MagicMock(**self.source_objects)
        modules.update(self.get_compatibility_modules(self.METRIC_SOURCE,
                                                      hqlib_metric_source))

        with patch.dict('sys.modules', modules):
            ictu = importlib.import_module('ictu')
            setattr(ictu, 'person', MagicMock())
            ictu_metric_source = importlib.import_module('ictu.metric_source')
            ictu_convention = importlib.import_module('ictu.convention')
            setattr(ictu, 'metric_source', ictu_metric_source)
            modules.update(self.get_compatibility_modules('ictu', ictu))
            modules.update(self.get_compatibility_modules('ictu.convention',
                                                          ictu_convention))
            modules.update(self.get_compatibility_modules('ictu.metric_source',
                                                          ictu_metric_source))

        return modules

    def load_definition(self, filename: str, contents: Union[str, bytes]) -> None:
        with patch('sys.path', sys.path + [self.sys_path]):
            super().load_definition(filename, contents)

    def filter_domain_object(self, mock_object: Mock) -> bool:
        return isinstance(mock_object, self.DOMAIN_CLASSES)

    def _merge(self, name: str, new_data: Mapping[str, Set[SourceUrl]]):
        for key, value in new_data.items():
            if isinstance(value, set):
                self.data[name].setdefault(key, set())
                self.data[name][key].update(value)
            else:
                self.data[name][key] = value

    def parse_domain_call(self, mock_object: Mock, args: Sequence[Any],
                          keywords: Mapping[str, Any]) -> None:
        if "name" in keywords:
            name = str(keywords["name"])
        elif len(args) > 1:
            name = str(args[1])
        else:
            # Likely a call to a superclass constructor
            return

        domain_name = str(mock_object.__class__.__name__)
        logging.debug('Name: %s Domain: %s', name, domain_name)

        self.data.setdefault(name, {})
        self._merge(name, self._parse_sources(keywords,
                                              "metric_source_ids",
                                              domain_name,
                                              from_key=True))
        self._merge(name, self._parse_sources(keywords, "metric_sources",
                                              domain_name,
                                              from_key=False))

    def _parse_sources(self, keywords: Mapping[str, Any], keyword: str,
                       domain_name: str, from_key: bool = True) -> Dict[str, Set[SourceUrl]]:
        sources: Dict[str, Set[SourceUrl]] = {}
        if keyword not in keywords:
            return sources

        if not isinstance(keywords[keyword], dict):
            logging.debug('keyword %s does not hold a dict', keyword)
            return sources

        for key, items in list(keywords[keyword].items()):
            if isinstance(items, (list, tuple)):
                sequence: Sequence[Union[Type, str]] = items
            else:
                sequence = [items]

            for value in sequence:
                class_name, source_value = \
                    self._parse_source_value(key, value, domain_name, from_key)

                if class_name is not None:
                    sources.setdefault(class_name, set())
                    sources[class_name].add(source_value)

        return sources

    @staticmethod
    def _get_source_url(source: domain.DomainObject) -> Optional[str]:
        if isinstance(source, MagicMock): # type: ignore[misc]
            return source.call_args_list[0][0][0]

        return source.url()

    def _parse_source_value(self, key: SourceID, value: Union[SourceID, str],
                            domain_name: str, from_key: bool) \
            -> Tuple[Optional[str], SourceUrl]:
        if from_key and isinstance(key, domain.DomainObject) and \
            isinstance(key, self.source_types):
            return self._parse_source_key(key, value, domain_name)

        if not from_key and isinstance(value, domain.DomainObject) and \
            isinstance(value, self.source_types):
            class_name = self.get_class_name(value)
            logging.debug('Class name: %s', class_name)

            source_url = self._get_source_url(value)
            if source_url is not None:
                return class_name, source_url

        return None, None

    def _parse_source_key(self, key: domain.DomainObject,
                          value: Union[SourceID, str], domain_name: str) \
            -> Tuple[Optional[str], SourceUrl]:
        source_url: SourceUrl = None
        source_value: str = str(value)
        class_name = self.get_class_name(key)
        url = self._get_source_url(key)
        if url is None or url in self.DUMMY_URLS or source_value.startswith(url):
            source_url = source_value
        elif class_name in self.SOURCE_ID_SOURCES and \
            source_value not in self.DUMMY_URLS:
            source_url = (url, source_value, domain_name)
            if domain_name in self.SOURCES_DOMAIN_FILTER:
                return None, None
        else:
            source_url = url

        return class_name, source_url

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

    def filter_domain_object(self, mock_object: Mock) -> bool:
        return isinstance(mock_object, domain.DomainObject)

    def get_hqlib_submodules(self) -> Dict[str, Mock]:
        return {
            "metric": MagicMock(**metric.__dict__)
        }

    def get_mock_modules(self) -> Dict[str, ModuleType]:
        modules = super().get_mock_modules()

        ictu = MagicMock()
        ictu_convention = MagicMock()
        ictu_metric_source = MagicMock()

        modules.update(self.get_compatibility_modules('ictu', ictu))
        modules.update(self.get_compatibility_modules('ictu.convention',
                                                      ictu_convention))
        modules.update(self.get_compatibility_modules('ictu.metric_source',
                                                      ictu_metric_source))

        return modules

    def parse_domain_call(self, mock_object: Mock, args: Sequence[Any],
                          keywords: Mapping[str, Any]) -> None:
        """
        Retrieve metric targets from a singular call within the project
        definition, which may have redefined metric options.
        """

        if "name" in keywords:
            name = str(keywords["name"])
        else:
            name = ""

        metric_options = keywords.get("metric_options")
        if isinstance(metric_options, dict):
            for metric_type, options in metric_options.items():
                self.parse_metric(name, metric_type, options=options)

        for old_keyword, new_key in self._old_metric_options.items():
            old = keywords.get(old_keyword)
            if isinstance(old, dict):
                for metric_type, option in old.items():
                    self.parse_metric(name, metric_type,
                                      options={new_key: option},
                                      options_type='old_options')

    @staticmethod
    def _get_target(value: Union[float, int, str, LooseVersion]) -> str:
        if isinstance(value, LooseVersion):
            version = value.version
            parts = tuple(part for part in version if isinstance(part, int))
            value = version_number_to_numerical(parts)

        return str(int(value))

    def parse_metric(self, name: str, metric_type: Type[domain.Metric],
                     options: Optional[Dict[str, Any]] = None,
                     options_type: str = 'metric_options'):
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

        metric_name = f'{class_name}{name}'
        if metric_name in self.data:
            targets: Dict[str, str] = self.data[metric_name]
        elif isinstance(metric_type, Mock): # type: ignore[misc]
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
                    'low_target': self._get_target(metric_type.low_target_value),
                    'target': self._get_target(metric_type.target_value),
                    'type': options_type,
                    'comment': ''
                }
            except (TypeError, ValueError, AttributeError):
                # Could not parse targets as integers
                return

        for key in ('low_target', 'target', 'comment'):
            value = options.get(key)
            if value is not None:
                if isinstance(value, str):
                    targets[key] = parse_unicode(value)
                else:
                    targets[key] = str(value)

        targets.update(self.parse_debt_target(options))
        targets.update({
            'base_name': class_name,
            'domain_name': name
        })

        self.data[metric_name] = targets

    def parse_debt_target(self, options: Dict[str, Any]) -> Dict[str, str]:
        """
        Retrieve data regarding a technical debt target.
        """

        if 'debt_target' in options:
            debt = options['debt_target']
            if not isinstance(debt, domain.TechnicalDebtTarget):
                return {}

            datetime_args = {'now.return_value': self.file_time}
            with patch('datetime.datetime', **datetime_args): # type: ignore
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
