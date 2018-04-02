"""
Retrieve historical data from Sonar and output it in a format similar to that
of the quality reporting dashboard history.
"""

import argparse
import datetime
import os
import logging
import ssl
from hqlib import domain
from hqlib.metric_source import Sonar
try:
    from hqlib.metric_source import CompactHistory
except ImportError:
    raise ImportError('Cannot import CompactHistory: quality_reporting 2.3.0+ required')
from hqlib.requirement import CodeQuality
from hqlib.metric_source.url_opener import UrlOpener
from gatherer.config import Configuration
from gatherer.log import Log_Setup
from gatherer.utils import get_datetime, Iterator_Limiter

def format_private_method(class_type, method, is_name=False):
    """
    Format a private method name according to PEP 8, where double underscores
    are replaced by an underscore, the class name and two underscores.

    The `class_type` is the class object where the method is defined, and
    `method` is the method or function object itself. If `is_name` is `True`,
    then this is instead the method name, excluding the double underscores.
    """

    if is_name:
        method_name = '__{}'.format(method)
    else:
        method_name = method.__name__

    return '_{}{}'.format(class_type.__name__, method_name)

def override(class_type):
    """
    Override a decorated method from a parent class `class_type`.
    """

    def overridden(func):
        """
        Use the decorated function `func` to provide as an overridden variant
        of the private method in the parent class.
        """

        setattr(class_type, format_private_method(class_type, func), func)

        return func

    return overridden

def reprovide(*methods):
    """
    Inherit some 'private' methods from a parent class for the decorated class.

    The arguments are method names without their double underscore prefix.
    """

    def reprovided(class_type):
        """
        Apply the private parent methods on the inheriting class `class_type`.

        If a method cannot be found in the direct bases of the class, then
        an `AttributeError` is raised.
        """

        for method in methods:
            for base in class_type.__bases__:
                parent_method = format_private_method(base, method, True)
                if hasattr(base, parent_method):
                    setattr(class_type,
                            format_private_method(class_type, method, True),
                            getattr(base, parent_method))
                    break
            else:
                raise AttributeError("Cannot find overridable private method {}".format(method))

        return class_type

    return reprovided

@reprovide("has_project", "get_json", "add_branch_param_to_url")
class Sonar_Time_Machine(Sonar):
    """
    Sonar instance with time machine history search support.
    """

    def __init__(self, sonar_url, *args, **kwargs):
        super(Sonar_Time_Machine, self).__init__(sonar_url, *args, **kwargs)

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

    @override(Sonar)
    def __metric(self, product, metric_name, branch):
        if not self.__has_project(product, branch):
            return -1

        metric_url = self.__sonar_url + 'api/timemachine/index?' + \
            'resource={component}&metrics={metric}'
        measures_url = self.__sonar_url + 'api/measures/search_history?' + \
            'component={component}&metrics={metric}'
        api_options = [
            (self.__add_branch_param_to_url(measures_url, branch),
             lambda json: json['measures'][0]['history'],
             ('date', 'value')),
            (self.__add_branch_param_to_url(metric_url, branch),
             lambda json: json[0]['cells'], ('d', 'v'))
        ]
        for api_url, data_getter, keys in api_options:
            url = api_url.format(component=product, metric=metric_name)
            if url not in self.__failed_urls:
                try:
                    json = self.__get_json(url)
                    return self.__parse_measures(data_getter(json), keys)
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
                json = self.__get_json(url)
                has_content = json['total'] > iterator_limiter.skip + json['ps']
                for issue in json['issues']:
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

    @override(Sonar)
    def __rule_violation(self, product, rule_name, default=0, branch=None):
        if not self.__has_project(product, branch):
            return -1

        rule_violation_url = self.__sonar_url + 'api/issues/search?' + \
            'componentRoots={component}&rules={rule}&p={p}&ps={ps}'
        rule_violation_url = self.__add_branch_param_to_url(rule_violation_url,
                                                            branch)
        return self.__count_issues(rule_violation_url, closed=False,
                                   component=product, rule=rule_name,
                                   default=default)

    @override(Sonar)
    def __false_positives(self, product, default=0, branch=None):
        if not self.__has_project(product, branch):
            return -1

        false_positives_url = self.__sonar_url + 'api/issues/search?' + \
            'componentRoots={component}&' + \
            'resolutions=FALSE-POSITIVE&p={p}&ps={ps}'
        false_positives_url = self.__add_branch_param_to_url(false_positives_url,
                                                             branch)
        return self.__count_issues(false_positives_url, closed=True,
                                   default=default, component=product)

def retrieve(url, name, products, username="", password=""):
    """
    Retrieve Sonar metrics from the instance at `url`, of the project `name`,
    and for the component names in the list `products`.
    """

    sonar = Sonar_Time_Machine(url, username=username, password=password)
    project = domain.Project(name=name, metric_sources={Sonar: sonar})
    history = CompactHistory('history-{}.json'.format(name))
    for product in products:
        retrieve_product(sonar, history, project, product)

def retrieve_product(sonar, history, project, product):
    """
    Retrieve Sonar metrics from the instance at `url`, of the project `name`,
    and for the component name `product`.
    """

    component = domain.Component(name=product,
                                 metric_source_ids={sonar: product})
    requirement = CodeQuality()
    metric_classes = requirement.metric_classes()
    metrics = []
    for metric_class in metric_classes:
        metrics.append(metric_class(subject=component, project=project))

    has_next_date = True
    while has_next_date:
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
    parser.add_argument('--name', help='Project name')
    parser.add_argument('--products', nargs='+', help='Sonar products')

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

    retrieve(args.url, args.name, args.products,
             username=username, password=password)

if __name__ == '__main__':
    main()
