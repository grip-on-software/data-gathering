"""
Retrieve historical data from Sonar and output it in a format similar to that
of the quality reporting dashboard history.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University

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

from argparse import ArgumentParser, Namespace
from datetime import datetime
import itertools
import json
import logging
import os
from pathlib import Path
import ssl
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, \
    Type, Union
import urllib
from hqlib import domain
from hqlib.metric_source import Sonar, Sonar7
from hqlib.metric_source.sonar import extract_branch_decorator
try:
    from hqlib.metric_source import CompactHistory
except ImportError as _error:
    raise ImportError('Cannot import CompactHistory: quality_reporting 2.3.0+ required') from _error
from hqlib.requirement import CodeQuality, ViolationsByType
from hqlib.metric_source.url_opener import UrlOpener
from hqlib.domain import Metric, LowerIsBetterMetric
from hqlib.metric.metric_source_mixin import SonarMetric
from hqlib.typing import MetricValue, Number
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.domain import source
from gatherer.log import Log_Setup
from gatherer.utils import format_date, get_datetime, Iterator_Limiter

SearchHistory = Dict[str,
                     Union[Dict[str, int],
                           List[Dict[str, Union[str, List[Dict[str, str]]]]]]]

class Custom_Metric(SonarMetric, LowerIsBetterMetric):
    """
    A custom metric from Sonar.
    """

    target_value = 0
    low_target_value = 100

    @classmethod
    def build_name(cls, name: str) -> str:
        """
        Format a metric class name for stable IDs from a Sonar metric name.
        """

        return ''.join(part.title() for part in name.split('_'))

    def __init__(self, name: str, subject: Optional[Any] = None,
                 project: Optional[domain.Project] = None) -> None:
        self._metric_name = name
        super().__init__(subject, project)

    def get_name(self) -> str:
        """
        Retrieve the custom metric name.
        """

        return self.build_name(self._metric_name)

    def stable_id(self) -> str:
        name = self.get_name()
        try:
            name += self._subject.name()
        except AttributeError:
            name += str(self._subject)

        return name

    def value(self) -> MetricValue:
        if isinstance(self._metric_source, Sonar_Time_Machine):
            val = self._metric_source.custom(self._sonar_id(),
                                             metric_name=self._metric_name)
        else:
            val = -1

        return val

class Sonar_Time_Machine(Sonar7):
    """
    Sonar instance with time machine history search support.
    """

    def __init__(self, sonar_url: str, from_date: Optional[str], *args: Any,
                 **kwargs: Any) -> None:
        super().__init__(sonar_url, *args, **kwargs)
        setattr(self, '__class__', Sonar_Time_Machine)

        self.__failed_urls: Set[str] = set()
        if from_date is not None:
            self.__from_datetime = get_datetime(from_date)
        else:
            self.__from_datetime = datetime(1, 1, 1)

        self.__current_datetime = self.__from_datetime
        self.__end_datetime = datetime.now()
        self.__next_datetime: Optional[datetime] = None
        self.__has_next_page = False
        self._reset()

    def _reset(self) -> None:
        self.__current_datetime = self.__from_datetime
        self.__end_datetime = datetime.now()
        self.__next_datetime = None
        self.__iterator = Iterator_Limiter(size=100, maximum=100000)
        self.__has_next_page = False

    def set_datetime(self, date: Optional[datetime] = None) -> None:
        """
        Alter the moment in time at which to check the Sonar state.
        """

        if date is None:
            if self.__next_datetime is None:
                raise RuntimeError('Cannot set next datetime')
            if self.__next_datetime == self.__end_datetime and self.__has_next_page:
                self.__iterator.update()
                self.__has_next_page = False

            date = self.__next_datetime
            self.__next_datetime = None

        self.__current_datetime = date

    def reset_datetime(self) -> None:
        """
        Alter the moment in time to the full initial range.
        """

        self._reset()

    def get_datetime(self) -> Optional[datetime]:
        """
        Retrieve the moment in time at which to check the Sonar state.
        """

        return self.__next_datetime

    @staticmethod
    def __make_datetime(date: str) -> datetime:
        return get_datetime(date[:-5], '%Y-%m-%dT%H:%M:%S')

    def __parse_measures(self, data: Sequence[Mapping[str, str]],
                         keys: Tuple[str, str]) -> Number:
        date_key, value_key = keys

        if data:
            self.__end_datetime = self.__make_datetime(str(data[-1][date_key]))

        for metric in data:
            date = self.__make_datetime(metric[date_key])
            if self.__current_datetime < date <= self.__end_datetime:
                if self.__next_datetime is not None and self.__next_datetime != date:
                    logging.warning('Measurement dates differ: %s %s',
                                    self.__next_datetime, date)
                self.__next_datetime = date
                if value_key not in metric:
                    return -1
                if isinstance(metric[value_key], list):
                    return float(metric[value_key][0])

                return float(metric[value_key])

        logging.warning('Outside of metrics measurement date range: %s %s',
                        self.__current_datetime, self.__end_datetime)
        return -1

    @staticmethod
    def _check_paging(iterator_limiter: Iterator_Limiter,
                      paging: Dict[str, int]) -> bool:
        size = iterator_limiter.skip + paging['pageSize']
        has_content = paging['total'] > size
        return iterator_limiter.check(has_content)

    def _update_page(self, data: SearchHistory) -> None:
        paging = data.get('paging')
        if not isinstance(paging, dict):
            return

        self.__has_next_page = self._check_paging(self.__iterator, paging)

    def _get_json(self, url: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        result = super()._get_json(url, *args, **kwargs)
        if not isinstance(result, dict):
            return {}

        return result

    def _metric(self, product: str, metric_name: str, branch: str) -> Number:
        if not self._has_project(product, branch):
            return -1

        api_url = self.url() + 'api/measures/search_history?' + \
            'component={component}&metrics={metric}&from={from_date}&' + \
            'p={p}&ps={ps}'
        keys = ('date', 'value')
        from_date = format_date(self.__from_datetime,
                                '%Y-%m-%dT%H:%M:%S+0000')
        url = api_url.format(component=urllib.parse.quote(product),
                             metric=urllib.parse.quote(metric_name),
                             from_date=urllib.parse.quote(from_date),
                             p=self.__iterator.page,
                             ps=self.__iterator.size)
        if url not in self.__failed_urls:
            try:
                data: SearchHistory = self._get_json(url)
                self._update_page(data)

                measures = data.get('measures')
                if not isinstance(measures, list):
                    return -1

                history = measures[0].get('history')
                if not isinstance(history, list):
                    return -1

                return self.__parse_measures(history, keys)
            except UrlOpener.url_open_exceptions:
                self.__failed_urls.add(url)

        logging.warning("Can't get %s value for %s from any of URLs",
                        metric_name, product)
        return -1

    def __count_issues(self, url: str, closed: bool = False,
                       default: int = -1, **url_params: str) -> int:
        count = 0
        check = True
        iterator_limiter = Iterator_Limiter(size=100, maximum=100000)
        while check:
            url = url.format(p=iterator_limiter.page,
                             ps=iterator_limiter.size,
                             **url_params)
            try:
                data = self._get_json(url)
                check = self._check_paging(iterator_limiter, data['paging'])
                count += self.__count_issue_data(data['issues'], closed)
                iterator_limiter.update()
            except UrlOpener.url_open_exceptions:
                logging.exception("Can't get value from %s", url)
                return default

        return count

    def __count_issue_data(self, issues: Sequence[Mapping[str, Any]],
                           closed: bool) -> int:
        count = 0
        for issue in issues:
            creation_date = self.__make_datetime(issue['creationDate'])
            if creation_date > self.__current_datetime:
                continue

            if 'closeDate' not in issue:
                if not closed:
                    count += 1
            else:
                close_date = self.__make_datetime(issue['closeDate'])
                if (closed and close_date < self.__current_datetime) or \
                    (not closed and close_date > self.__current_datetime):
                    count += 1

        return count

    def _rule_violation(self, product: str, rule_name: str, default: int = 0,
                        branch: str = '') -> int:
        if not self._has_project(product, branch):
            return -1

        rule_violation_url = self.url() + 'api/issues/search?' + \
            'componentRoots={component}&rules={rule}&p={p}&ps={ps}'
        rule_violation_url = self._add_branch_param_to_url(rule_violation_url,
                                                           branch)
        return self.__count_issues(rule_violation_url, closed=False,
                                   component=product, rule=rule_name,
                                   default=default)

    def _false_positives(self, product: str, branch: str) -> int:
        if not self._has_project(product, branch):
            return -1

        false_positives_url = self.url() + 'api/issues/search?' + \
            'componentRoots={component}&' + \
            'resolutions=FALSE-POSITIVE&p={p}&ps={ps}'
        false_positives_url = self._add_branch_param_to_url(false_positives_url,
                                                            branch)
        return self.__count_issues(false_positives_url, closed=True,
                                   default=0, component=product)

    _issues_by_type_api_url = 'api/issues/search?' + \
        'componentRoots={component}&types={type}&p={p}&ps={ps}'

    @extract_branch_decorator
    def maintainability_bugs(self, product: str, branch: str) -> int:
        bugs_url = self.url() + 'api/issues/search?' + \
            'componentRoots={component}&types=BUG&p={p}&ps={ps}'
        return self.__count_issues(bugs_url, closed=False, default=0,
                                   component=product)

    @extract_branch_decorator
    def vulnerabilities(self, product: str, branch: str) -> int:
        vulnerabilities_url = self.url() + 'api/issues/search?' + \
            'componentRoots={component}&types=VULNERABILITY&p={p}&ps={ps}'
        return self.__count_issues(vulnerabilities_url, closed=False, default=0,
                                   component=product)

    @extract_branch_decorator
    def code_smells(self, product: str, branch: str) -> int:
        code_smells_url = self.url() + 'api/issues/search?' + \
            'componentRoots={component}&types=CODE_SMELL&p={p}&ps={ps}'
        return self.__count_issues(code_smells_url, closed=False, default=0,
                                   component=product)

    @extract_branch_decorator
    def custom(self, product: str, branch: str, metric_name: str = '') -> int:
        """
        Retrieve a custom metric.
        """

        return int(self._metric(product, metric_name, branch))

def retrieve(sonar: Sonar_Time_Machine, project: Project,
             products: Sequence[Union[str, Mapping[str, str]]],
             metrics: Sequence[str]) -> Set[str]:
    """
    Retrieve Sonar metrics from the instance at `url`, of the project `name`,
    and for the component names in the list `products`.
    """

    hq_project = domain.Project(name=project.key,
                                metric_sources={Sonar: sonar})

    history_path = project.export_key / 'data_history.json'
    with history_path.open('w', encoding='utf-8') as history_file:
        json.dump({"dates": [], "statuses": [], "metrics": {}}, history_file)

    history = CompactHistory(str(history_path))
    metric_names = set()
    for product in products:
        metric_names.update(retrieve_product(sonar, history, hq_project,
                                             product, metrics))

    return metric_names

def retrieve_product(sonar: Sonar_Time_Machine, history: CompactHistory,
                     project: domain.Project,
                     product: Union[str, Mapping[str, str]],
                     include_metrics: Sequence[str]) -> Set[str]:
    """
    Retrieve Sonar metrics from the instance described by the domain object
    `sonar`, of the project `project`, and for the component name `product`.
    The results are added to the `history` object.
    """

    if isinstance(product, dict):
        source_id = product["source_id"]
        product_name = product["domain_name"]
    else:
        source_id = product
        product_name = product

    sonar.reset_datetime()
    component = domain.Component(name=product_name,
                                 metric_source_ids={sonar: source_id})
    requirements = (CodeQuality(), ViolationsByType())
    metric_classes = tuple(itertools.chain(*[
        requirement.metric_classes() for requirement in requirements
    ]))
    metrics, metric_names = get_metrics(metric_classes, include_metrics,
                                        component, project)
    if not metrics:
        return metric_names

    has_next_date = True
    while has_next_date:
        # Clear caches and reload
        for metric in metrics:
            metric.status.cache_clear()
            metric.value()

        date = sonar.get_datetime()
        if date is not None:
            history.add_metrics(date, metrics)

        try:
            sonar.set_datetime()
        except RuntimeError:
            has_next_date = False
            logging.warning('Cannot obtain next measurement date')

    return metric_names

def get_metrics(metric_classes: Sequence[Type[Metric]],
                include_metrics: Sequence[str],
                component: Optional[domain.Component] = None,
                project: Optional[domain.Project] = None) \
                    -> Tuple[List[Metric], Set[str]]:
    """
    Retrieve metric objects that we wish to collect from the Sonar source, based
    upon `metric_classes`, a list of required metric classes, and
    `include_metrics`, a list of metric names to filter on and/or include
    custom metrics. The metrics are initialized with the provided `component`
    and `project`, or if both are `None`, then only the metric names are
    provided.
    """

    metrics = []
    metric_names = set()
    has_parameters = component is not None and project is not None

    for metric_class in metric_classes:
        if 'all' in include_metrics or metric_class.__name__ in include_metrics:
            if has_parameters:
                metrics.append(metric_class(subject=component, project=project))

            metric_names.add(metric_class.__name__)

    for metric in include_metrics:
        if metric not in metric_names and metric != 'all':
            if has_parameters:
                custom = Custom_Metric(metric, subject=component,
                                       project=project)
                metrics.append(custom)

            metric_names.add(Custom_Metric.build_name(metric))

    return metrics, metric_names

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()
    if config.has_section('sonar'):
        sonar = dict(config.items('sonar'))
        verify_config = config.get('sonar', 'verify')
        verify: Union[bool, str] = verify_config
        if not Configuration.has_value(verify_config):
            verify = False
        elif not Path(verify_config).exists():
            verify = True
    else:
        sonar = {
            'host': '',
            'username': '',
            'password': ''
        }
        verify = True

    description = "Obtain sonar history and output JSON"
    parser = ArgumentParser(description=description)
    parser.add_argument('project', help='Project key')
    parser.add_argument('--url', help='Sonar URL', default=sonar['host'])
    parser.add_argument('--no-url', action='store_const', const='', dest='url',
                        help='Do not use the sonar URL from settings')
    parser.add_argument('--username', help='Sonar username',
                        default=sonar['username'])
    parser.add_argument('--password', help='Sonar password',
                        default=sonar['password'])
    parser.add_argument('--verify', nargs='?', const=True, default=verify,
                        help='Enable SSL certificate verification')
    parser.add_argument('--no-verify', action='store_false', dest='verify',
                        help='Disable SSL certificate verification')
    parser.add_argument('--products', nargs='+', help='Sonar products')
    parser.add_argument('--metrics', nargs='*', default=['all'],
                        help='Quality report metrics')
    parser.add_argument('--from-date', dest='from_date',
                        help='Date to start collecting data from')
    parser.add_argument('--names', default='metrics_base_names.json',
                        help='File to add metric base names to')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def adjust_verify(verify: Union[bool, str]) -> None:
    """
    Adjust SSL certificate verification for the Sonar source.
    """

    if verify is False:
        logging.critical('SSL certificate verification cannot be disabled for Sonar export')
    elif isinstance(verify, str):
        cafile_env = ssl.get_default_verify_paths().openssl_cafile_env
        os.environ[cafile_env] = verify

def get_products(products: Optional[Sequence[str]], project: Project) \
        -> List[Union[str, Dict[str, str]]]:
    """
    Retrieve a list of product components to collect for the project.
    """

    if products is None:
        sources_path = project.export_key / 'data_source_ids.json'
        if not sources_path.exists():
            logging.warning('No Sonar products defined for project %s',
                            project.key)
            return []

        with sources_path.open('r', encoding='utf-8') as source_ids:
            products = [
                product for product in json.load(source_ids)
                if product.get("source_type", "sonar") == "sonar"
            ]

    return list(products)

def update_metric_names(filename: str, metric_names: Set[str]) -> None:
    """
    Update a JSON file with metric base names to contain the collected base
    names.
    """

    path = Path(filename)
    if path.exists():
        with path.open('r', encoding='utf-8') as input_file:
            metric_names.update(json.load(input_file))

    with path.open('w', encoding='utf-8') as output_file:
        json.dump(list(metric_names), output_file)

def get_sonar_url(project: Project) -> str:
    """
    Retrieve the URL to the Sonar instance of the project, from project
    sources, or return an empty string if the source is unavailable or its
    version is not known.
    """

    sonar_source = project.sources.find_source_type(source.Sonar)
    if not sonar_source:
        logging.warning('No Sonar URL defined for project %s', project.key)
        return ""

    if sonar_source.version == "":
        logging.warning('Cannot determine Sonar version for project %s',
                        project.key)
        return ""

    return sonar_source.url

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()
    username = ""
    if Configuration.has_value(args.username):
        username = args.username

    password = ""
    if Configuration.has_value(args.password):
        password = args.password

    adjust_verify(args.verify)

    project = Project(args.project)
    project.make_export_directory()

    names = str(args.names)
    url = ""
    metrics: List[str] = args.metrics
    if Configuration.has_value(args.url):
        url = args.url
    else:
        url = get_sonar_url(project)
        if url == "":
            metric_names = get_metrics([], metrics)[1]
            update_metric_names(names, metric_names)
            return

    products = get_products(args.products, project)

    update_filename = project.export_key / 'history_update.json'
    from_date: Optional[str] = args.from_date
    dates: Dict[str, str] = {}
    if update_filename.exists():
        with update_filename.open('r', encoding='utf-8') as update_file:
            dates = json.load(update_file)

    if from_date is None:
        for metric in metrics:
            from_date = dates.get(metric, from_date)

    sonar = Sonar_Time_Machine(url, from_date, username=username,
                               password=password)
    metric_names = retrieve(sonar, project, products, metrics)

    for metric in metrics:
        dates[metric] = format_date(datetime.now())

    with update_filename.open('w', encoding='utf-8') as update_file:
        json.dump(dates, update_file)

    update_metric_names(names, metric_names)

if __name__ == '__main__':
    main()
