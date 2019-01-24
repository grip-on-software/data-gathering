"""
Retrieve historical data from Sonar and output it in a format similar to that
of the quality reporting dashboard history.
"""

import argparse
import datetime
import json
import os
import logging
import ssl
import urllib
from hqlib import domain
from hqlib.metric_source import Sonar, Sonar7
from hqlib.metric_source.sonar import extract_branch_decorator
try:
    from hqlib.metric_source import CompactHistory
except ImportError:
    raise ImportError('Cannot import CompactHistory: quality_reporting 2.3.0+ required')
from hqlib.requirement import CodeQuality
from hqlib.metric_source.url_opener import UrlOpener
from hqlib.domain import LowerIsBetterMetric
from hqlib.metric.metric_source_mixin import SonarMetric
from gatherer.config import Configuration
from gatherer.domain import Project
from gatherer.domain import source
from gatherer.log import Log_Setup
from gatherer.utils import format_date, get_datetime, Iterator_Limiter

class Custom_Metric(SonarMetric, LowerIsBetterMetric):
    """
    A custom metric from Sonar.
    """

    target_value = 0
    low_target_value = 100

    @classmethod
    def build_name(cls, name):
        """
        Format a metric class name for stable IDs from a Sonar metric name.
        """

        return ''.join(part.title() for part in name.split('_'))

    def __init__(self, name, subject=None, project=None):
        self._metric_name = name
        super(Custom_Metric, self).__init__(subject, project)

    def get_name(self):
        """
        Retrieve the custom metric name.
        """

        return self.build_name(self._metric_name)

    def stable_id(self):
        name = self.get_name()
        name += self._subject.name()
        return name

    def value(self):
        if self._metric_source:
            val = self._metric_source.custom(self._sonar_id(),
                                             metric_name=self._metric_name)
        else:
            val = -1

        return val

class Sonar_Time_Machine(Sonar7):
    """
    Sonar instance with time machine history search support.
    """

    def __init__(self, sonar_url, from_date, *args, **kwargs):
        super(Sonar_Time_Machine, self).__init__(sonar_url, *args, **kwargs)
        setattr(self, '__class__', Sonar_Time_Machine)

        self.__current_datetime = None
        self.__end_datetime = None
        self.__next_datetime = None
        self.__failed_urls = set()
        self.__iterator = None
        self.__has_next_page = False
        if from_date is not None:
            self.__from_datetime = get_datetime(from_date)
        else:
            self.__from_datetime = datetime.datetime(1, 1, 1)
        self.reset_datetime()

    def set_datetime(self, date=None):
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

    def reset_datetime(self):
        """
        Alter the moment in time to the full initial range.
        """

        self.__current_datetime = self.__from_datetime
        self.__end_datetime = datetime.datetime.now()
        self.__next_datetime = None
        self.__iterator = Iterator_Limiter(size=100, maximum=100000)
        self.__has_next_page = False

    def get_datetime(self):
        """
        Retrieve the moment in time at which to check the Sonar state.
        """

        return self.__next_datetime

    @staticmethod
    def __make_datetime(date):
        return get_datetime(date[:-5], '%Y-%m-%dT%H:%M:%S')

    def __parse_measures(self, data, keys):
        date_key, value_key = keys

        if data:
            self.__end_datetime = self.__make_datetime(data[-1][date_key])

        for metric in data:
            date = self.__make_datetime(metric[date_key])
            if self.__current_datetime < date <= self.__end_datetime:
                if self.__next_datetime is not None and self.__next_datetime != date:
                    logging.warning('Measurement dates differ: %s %s',
                                    self.__next_datetime, date)
                self.__next_datetime = date
                if isinstance(metric[value_key], list):
                    return float(metric[value_key][0])

                return float(metric[value_key])

        logging.warning('Outside of metrics measurement date range: %s %s',
                        self.__current_datetime, self.__end_datetime)
        return -1

    def _update_page(self, data):
        size = self.__iterator.skip + data['paging']['pageSize']
        has_content = data['paging']['total'] > size
        self.__has_next_page = self.__iterator.check(has_content)

    def _metric(self, product, metric_name, branch):
        if not self._has_project(product, branch):
            return -1

        metric_url = self.url() + 'api/timemachine/index?' + \
            'resource={component}&metrics={metric}&fromDateTime={from_date}'
        measures_url = self.url() + 'api/measures/search_history?' + \
            'component={component}&metrics={metric}&from={from_date}'
        api_options = [
            (self._add_branch_param_to_url(measures_url, branch),
             lambda json: json['measures'][0]['history'],
             ('date', 'value')),
            (self._add_branch_param_to_url(metric_url, branch),
             lambda json: json[0]['cells'], ('d', 'v'))
        ]
        from_date = format_date(self.__from_datetime,
                                '%Y-%m-%dT%H:%M:%S+0000')
        for api_url, data_getter, keys in api_options:
            api_url = "{0}&p={{p}}&ps={{ps}}".format(api_url)
            url = api_url.format(component=urllib.parse.quote(product),
                                 metric=urllib.parse.quote(metric_name),
                                 from_date=urllib.parse.quote(from_date),
                                 p=self.__iterator.page,
                                 ps=self.__iterator.size)
            if url not in self.__failed_urls:
                try:
                    data = self._get_json(url)
                    self._update_page(data)
                    return self.__parse_measures(data_getter(data), keys)
                except UrlOpener.url_open_exceptions:
                    self.__failed_urls.add(url)

        logging.warning("Can't get %s value for %s from any of URLs",
                        metric_name, product)
        return -1

    def __count_issues(self, url, closed=False, default=-1, **url_params):
        count = 0
        has_content = True
        iterator_limiter = Iterator_Limiter(size=100, maximum=100000)
        while iterator_limiter.check(has_content):
            url = url.format(p=iterator_limiter.page,
                             ps=iterator_limiter.size,
                             **url_params)
            try:
                data = self._get_json(url)
                new_size = iterator_limiter.skip + data['paging']['pageSize']
                has_content = data['paging']['total'] > new_size
                for issue in data['issues']:
                    creation_date = self.__make_datetime(issue['creationDate'])
                    if creation_date > self.__current_datetime:
                        continue

                    if 'closeDate' not in issue:
                        if not closed:
                            count += 1
                    else:
                        close_date = self.__make_datetime(issue['closeDate'])
                        if closed and close_date < self.__current_datetime:
                            count += 1
                        elif not closed and close_date > self.__current_datetime:
                            count += 1

                iterator_limiter.update()
            except UrlOpener.url_open_exceptions:
                logging.exception("Can't get value from %s", url)
                return default

        return count

    def _rule_violation(self, product, rule_name, default=0, branch=None):
        if not self._has_project(product, branch):
            return -1

        rule_violation_url = self.url() + 'api/issues/search?' + \
            'componentRoots={component}&rules={rule}&p={p}&ps={ps}'
        rule_violation_url = self._add_branch_param_to_url(rule_violation_url,
                                                           branch)
        return self.__count_issues(rule_violation_url, closed=False,
                                   component=product, rule=rule_name,
                                   default=default)

    def _false_positives(self, product, default=0, branch=None):
        if not self._has_project(product, branch):
            return -1

        false_positives_url = self.url() + 'api/issues/search?' + \
            'componentRoots={component}&' + \
            'resolutions=FALSE-POSITIVE&p={p}&ps={ps}'
        false_positives_url = self._add_branch_param_to_url(false_positives_url,
                                                            branch)
        return self.__count_issues(false_positives_url, closed=True,
                                   default=default, component=product)

    @extract_branch_decorator
    def custom(self, product, branch, metric_name=None):
        """
        Retrieve a custom metric.
        """

        return int(self._metric(product, metric_name, branch))

def retrieve(sonar, project, products, metrics=None):
    """
    Retrieve Sonar metrics from the instance at `url`, of the project `name`,
    and for the component names in the list `products`.
    """

    hq_project = domain.Project(name=project.key,
                                metric_sources={Sonar: sonar})

    history_filename = os.path.join(project.export_key, 'data_history.json')
    with open(history_filename, 'w') as history_file:
        json.dump({"dates": [], "statuses": [], "metrics": {}}, history_file)

    history = CompactHistory(history_filename)
    metric_names = set()
    for product in products:
        metric_names.update(retrieve_product(sonar, history, hq_project,
                                             product, metrics))

    return metric_names

def retrieve_product(sonar, history, project, product, include_metrics=None):
    """
    Retrieve Sonar metrics from the instance described by the domain object
    `sonar`, of the project `project`, and for the component name `product`.
    The results are added to the `history` object.
    """

    if isinstance(product, dict):
        source_id = product["source_id"]
        product = product["domain_name"]
    else:
        source_id = product

    sonar.reset_datetime()
    component = domain.Component(name=product,
                                 metric_source_ids={sonar: source_id})
    requirement = CodeQuality()
    metric_classes = requirement.metric_classes()
    metrics, metric_names = get_metrics(metric_classes, include_metrics,
                                        component, project)

    has_next_date = True
    while has_next_date:
        # Clear caches and reload
        for metric in metrics:
            metric.status.cache_clear()
        metrics[0].value()

        date = sonar.get_datetime()
        if date is not None:
            history.add_metrics(date, metrics)

        try:
            sonar.set_datetime()
        except RuntimeError:
            has_next_date = False
            logging.warning('Cannot obtain next measurement date')

    return metric_names

def get_metrics(metric_classes=None, include_metrics=None, component=None,
                project=None):
    """
    Retrieve metric objects that we wish to collect from the Sonar source, based
    upon `metric_classes`, a list of required metric classes, and
    `include_metrics`, a list of metric names to filter on and/or include
    custom metrics. Either list may also be `None`. The metrics are initialized
    with the provided `component` and `project`, or if both are `None`, then
    only the metric names are provided.
    """

    metrics = []
    metric_names = set()

    if metric_classes is None:
        metric_classes = []
    if include_metrics is None:
        include_metrics = []

    for metric_class in metric_classes:
        if include_metrics is None or metric_class.__name__ in include_metrics:
            if component is not None and project is not None:
                metrics.append(metric_class(subject=component, project=project))

            metric_names.add(metric_class.__name__)

    for metric in include_metrics:
        if metric not in metric_names:
            if component is not None and project is not None:
                custom = Custom_Metric(metric, subject=component,
                                       project=project)
                metrics.append(custom)
                metric_names.add(custom.get_name())
            else:
                metric_names.add(Custom_Metric.build_name(metric))

    return metrics, metric_names

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()
    if config.has_section('sonar'):
        sonar = dict(config.items('sonar'))
        verify = config.get('sonar', 'verify')
        if not Configuration.has_value(verify):
            verify = False
        elif not os.path.exists(verify):
            verify = True
    else:
        sonar = {
            'host': None,
            'username': '',
            'password': ''
        }
        verify = True

    description = "Obtain sonar history and output JSON"
    parser = argparse.ArgumentParser(description=description)
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
    parser.add_argument('--metrics', nargs='*', help='Quality report metrics')
    parser.add_argument('--from-date', dest='from_date',
                        help='Date to start collecting data from')
    parser.add_argument('--names', default='metrics_base_names.json',
                        help='File to add metric base names to')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

def adjust_verify(verify):
    """
    Adjust SSL certificate verification for the Sonar source.
    """

    if verify is False:
        logging.critical('SSL certificate verification cannot be disabled for Sonar export')
    elif verify is not True:
        cafile_env = ssl.get_default_verify_paths().openssl_cafile_env
        os.environ[cafile_env] = verify

def get_products(products, project):
    """
    Retrieve a list of product components to collect for the project.
    """

    if products is None:
        sources_file = os.path.join(project.export_key, 'data_source_ids.json')
        if not os.path.exists(sources_file):
            logging.warning('No Sonar products defined for project %s',
                            project.key)
            return []

        with open(sources_file) as source_ids:
            products = json.load(source_ids)

    return products

def update_metric_names(filename, metric_names):
    """
    Update a JSON file with metric base names to contain the collected base
    names.
    """

    if os.path.exists(filename):
        with open(filename) as input_file:
            metric_names.update(json.load(input_file))

    with open(filename, 'w') as output_file:
        json.dump(list(metric_names), output_file)

def get_sonar_url(project):
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

def main():
    """
    Main entry point.
    """

    args = parse_args()
    if Configuration.has_value(args.username):
        username = args.username
    else:
        username = ""

    if Configuration.has_value(args.password):
        password = args.password
    else:
        password = ""

    adjust_verify(args.verify)

    project = Project(args.project)
    project.make_export_directory()

    if Configuration.has_value(args.url):
        url = args.url
    else:
        url = get_sonar_url(project)
        if url == "":
            metric_names = get_metrics(include_metrics=args.metrics)[1]
            update_metric_names(args.names, metric_names)
            return

    products = get_products(args.products, project)

    update_filename = os.path.join(project.export_key, 'history_update.json')
    from_date = args.from_date
    dates = {}
    if os.path.exists(update_filename):
        with open(update_filename) as update_file:
            dates = json.load(update_file)

    if from_date is None and args.metrics is not None:
        for metric in args.metrics:
            from_date = dates.get(metric)

    sonar = Sonar_Time_Machine(url, from_date, username=username,
                               password=password)
    metric_names = retrieve(sonar, project, products, metrics=args.metrics)

    if args.metrics is not None:
        for metric in args.metrics:
            dates[metric] = format_date(datetime.datetime.now())

    with open(update_filename, 'w') as update_file:
        json.dump(dates, update_file)

    update_metric_names(args.names, metric_names)

if __name__ == '__main__':
    main()
