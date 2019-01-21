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
from gatherer.utils import get_datetime, Iterator_Limiter

class Custom_Metric(SonarMetric, LowerIsBetterMetric):
    """
    A custom metric from Sonar.
    """

    target_value = 0
    low_target_value = 100

    def __init__(self, name, subject=None, project=None):
        self._metric_name = name
        super(Custom_Metric, self).__init__(subject, project)

    def stable_id(self):
        name = ''.join(part.title() for part in self._metric_name.split('_'))
        name += self._subject.name()
        return name

    def value(self):
        if self._metric_source:
            val = self._metric_source.custom(self._sonar_id(),
                                             metric_name=self._metric_name)
        else:
            val = -1

        print(repr(val))
        return val

class Sonar_Time_Machine(Sonar7):
    """
    Sonar instance with time machine history search support.
    """

    def __init__(self, sonar_url, *args, **kwargs):
        super(Sonar_Time_Machine, self).__init__(sonar_url, *args, **kwargs)
        self.__class__ = Sonar_Time_Machine

        self.__sonar_url = sonar_url
        self.__current_datetime = None
        self.__end_datetime = None
        self.__next_datetime = None
        self.__failed_urls = set()
        self.reset_datetime()

    def set_datetime(self, date=None):
        """
        Alter the moment in time at which to check the Sonar state.
        """

        if date is None:
            if self.__next_datetime is None:
                raise RuntimeError('Cannot set next datetime')

            date = self.__next_datetime
            self.__next_datetime = None

        self.__current_datetime = date

    def reset_datetime(self):
        """
        Alter the moment in time to the full initial range.
        """

        self.__current_datetime = datetime.datetime(1, 1, 1)
        self.__end_datetime = datetime.datetime.now()
        self.__next_datetime = None

    def get_datetime(self):
        """
        Retrieve the moment in time at which to check the Sonar state.
        """

        return self.__current_datetime

    @staticmethod
    def __make_datetime(date):
        return get_datetime(date[:-5], '%Y-%m-%dT%H:%M:%S')

    def __parse_measures(self, data, keys):
        date_key, value_key = keys
        for metric in data:
            date = self.__make_datetime(metric[date_key])
            if self.__current_datetime < date < self.__end_datetime:
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

    def _metric(self, product, metric_name, branch):
        if not self._has_project(product, branch):
            return -1

        metric_url = self.__sonar_url + 'api/timemachine/index?' + \
            'resource={component}&metrics={metric}'
        measures_url = self.__sonar_url + 'api/measures/search_history?' + \
            'component={component}&metrics={metric}'
        api_options = [
            (self._add_branch_param_to_url(measures_url, branch),
             lambda json: json['measures'][0]['history'],
             ('date', 'value')),
            (self._add_branch_param_to_url(metric_url, branch),
             lambda json: json[0]['cells'], ('d', 'v'))
        ]
        for api_url, data_getter, keys in api_options:
            url = api_url.format(component=product, metric=metric_name)
            if url not in self.__failed_urls:
                try:
                    data = self._get_json(url)
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

        rule_violation_url = self.__sonar_url + 'api/issues/search?' + \
            'componentRoots={component}&rules={rule}&p={p}&ps={ps}'
        rule_violation_url = self._add_branch_param_to_url(rule_violation_url,
                                                           branch)
        return self.__count_issues(rule_violation_url, closed=False,
                                   component=product, rule=rule_name,
                                   default=default)

    def _false_positives(self, product, default=0, branch=None):
        if not self._has_project(product, branch):
            return -1

        false_positives_url = self.__sonar_url + 'api/issues/search?' + \
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
    history = CompactHistory(history_filename)
    for product in products:
        retrieve_product(sonar, history, hq_project, product, metrics)

def retrieve_product(sonar, history, project, product, include_metrics=None):
    """
    Retrieve Sonar metrics from the instance described by the domain object
    `sonar`, of the project `project`, and for the component name `product`.
    The results are added to the `history` object.
    """

    component = domain.Component(name=product,
                                 metric_source_ids={sonar: product})
    requirement = CodeQuality()
    metric_classes = requirement.metric_classes()
    metrics = []
    metric_names = set()
    for metric_class in metric_classes:
        if include_metrics is None or metric_class.__name__ in include_metrics:
            metrics.append(metric_class(subject=component, project=project))
            metric_names.add(metric_class.__name__)

    for metric in include_metrics:
        if metric not in metric_names:
            metrics.append(Custom_Metric(metric, subject=component,
                                         project=project))

    has_next_date = True
    while has_next_date:
        # Clear caches and reload
        for metric in metrics:
            metric.status.cache_clear()
        metrics[0].value()

        try:
            sonar.set_datetime()
        except RuntimeError:
            has_next_date = False
            logging.warning('Cannot obtain next measurement date')

        history.add_metrics(sonar.get_datetime(), metrics)

def parse_args():
    """
    Parse command line arguments.
    """

    config = Configuration.get_settings()
    verify = config.get('sonar', 'verify')
    if not Configuration.has_value(verify):
        verify = False
    elif not os.path.exists(verify):
        verify = True

    description = "Obtain sonar history and output JSON"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('project', help='Project key')
    parser.add_argument('--url', help='Sonar URL',
                        default=config.get('sonar', 'host'))
    parser.add_argument('--username', help='Sonar username',
                        default=config.get('sonar', 'username'))
    parser.add_argument('--password', help='Sonar password',
                        default=config.get('sonar', 'password'))
    parser.add_argument('--verify', nargs='?', const=True, default=verify,
                        help='Enable SSL certificate verification')
    parser.add_argument('--no-verify', action='store_false', dest='verify',
                        help='Disable SSL certificate verification')
    parser.add_argument('--products', nargs='+', help='Sonar products')
    parser.add_argument('--metrics', nargs='+', help='Quality report metrics')

    Log_Setup.add_argument(parser)
    args = parser.parse_args()
    Log_Setup.parse_args(args)
    return args

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

    if args.verify is False:
        logging.critical('SSL certificate verification cannot be disabled for Sonar export')
    elif args.verify is not True:
        cafile_env = ssl.get_default_verify_paths().openssl_cafile_env
        os.environ[cafile_env] = args.verify

    project = Project(args.project)
    project.make_export_directory()

    sonar_source = project.sources.find_source_type(source.Sonar)
    if sonar_source:
        url = sonar_source.url
    elif Configuration.has_value(args.url):
        url = args.url
    else:
        logging.warning('No Sonar URL defined for project %s', project.key)
        return

    if args.products is not None:
        products = args.products
    else:
        sources_file = os.path.join(project.export_key, 'data_source_ids.json')
        if not os.path.exists(sources_file):
            logging.warning('No Sonar products defined for project %s',
                            project.key)
            return

        with open(sources_file) as source_ids:
            products = [domain.source_id for domain in json.load(source_ids)]

    sonar = Sonar_Time_Machine(url, username=username, password=password)
    retrieve(sonar, project, products, metrics=args.metrics)

if __name__ == '__main__':
    main()
