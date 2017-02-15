"""
Utilities for various parts of the data gathering chain.
"""

import bisect
import ConfigParser
import json
import os
import urlparse
from datetime import datetime

class Iterator_Limiter(object):
    """
    Class which keeps handles batches of queries and keeps track of iterator
    count, in order to limit batch processing.
    """

    def __init__(self, size=1000, maximum=10000000):
        self._skip = 0
        self._size = size
        self._max = maximum

    def check(self, had_content):
        """
        Check whether a loop condition to continue retrieving iterator data
        should still evaluate to true.
        """

        if had_content and self._size != 0 and not self.reached_limit():
            return True

        return False

    def reached_limit(self):
        """
        Check whether the hard limit of the iterator limiter has been reached.
        """

        if self._skip + self._size > self._max:
            return True

        return False

    def update(self):
        """
        Update the iterator counter after a batch, to prepare the next query.
        """

        self._skip += self._size
        if self.reached_limit():
            self._size = self._max - self._skip

    @property
    def size(self):
        """
        Retrieve the size of the next batch query.
        """

        return self._size

    @property
    def skip(self):
        """
        Retrieve the current iterator counter.
        """

        return self._skip

class Project(object):
    """
    Object that holds information about a certain project.

    This includes configuration such JIRA keys, long names, descriptions,
    locations of source repositories, credentials, and so on.

    The data is read from multiple sources, namely settings and gathered data,
    which is available on a case-by-case basis. Only data that has been gathered
    can be accessed.
    """

    _settings = None
    _credentials = None

    def __init__(self, project_key, follow_host_change=True):
        if self._settings is None:
            self._settings = ConfigParser.RawConfigParser()
            self._settings.read("settings.cfg")

        if self._credentials is None:
            self._credentials = ConfigParser.RawConfigParser()
            self._credentials.read("credentials.cfg")

        # JIRA project key
        self._project_key = project_key
        self._follow_host_change = follow_host_change

        # Long project name used in repositories and quality dashboard project
        # definitions.
        if self._settings.has_option('projects', self._project_key):
            self._project_name = self._settings.get('projects',
                                                    self._project_key)
        else:
            self._project_name = None

        if self._settings.has_option('subprojects', self._project_key):
            self._main_project = self._settings.get('subprojects',
                                                    self._project_key)
        else:
            self._main_project = None

        self._sources = None
        self._load_sources()

    def _load_sources(self):
        if self._sources is not None:
            return

        self._sources = []
        path = os.path.join(self.export_key, 'data_sources.json')
        if os.path.exists(path):
            with open(path, 'r') as sources_file:
                sources = json.load(sources_file)
                for source in sources:
                    self._sources.append(self._update_credentials(source))

    def _update_credentials(self, source):
        # Update the URL of a source when hosts change, and add any additional
        # credentials to the URL or source registry.
        parts = urlparse.urlsplit(source['url'])
        host = parts.netloc
        if self._credentials.has_section(host):
            if self._follow_host_change and self._credentials.has_option(host, 'host'):
                host = self._credentials.get(host, 'host')

            username = self._credentials.get(host, 'username')
            password = self._credentials.get(host, 'password')

            if self._credentials.has_option(host, 'gitlab_token'):
                source['gitlab_token'] = self._credentials.get(host,
                                                               'gitlab_token')

            host_parts = (parts.scheme, host, '', '', '')
            source['host'] = urlparse.urlunsplit(host_parts)

            auth = '{0}:{1}'.format(username, password)
            host = auth + '@' + host

        new_parts = (parts.scheme, host, parts.path, parts.query, parts.fragment)
        source['url'] = urlparse.urlunsplit(new_parts)
        return source

    def get_url_credentials(self, url):
        """
        Convert a URL to one that has credentials, if they can be found.
        """

        parts = urlparse.urlsplit(url)
        host = parts.netloc
        if self._credentials.has_section(host):
            username = self._credentials.get(host, 'username')
            password = self._credentials.get(host, 'password')

            auth = '{0}:{1}'.format(username, password)
            host = auth + '@' + host

        new_parts = (parts.scheme, host, parts.path, parts.query, parts.fragment)
        url = urlparse.urlunsplit(new_parts)
        return url

    @property
    def export_key(self):
        """
        Retrieve the key used for project data exports.
        """

        return self._project_key

    @property
    def jira_key(self):
        """
        Retrieve the key used for the JIRA project.
        """

        return self._project_key

    @property
    def gitlab_group_name(self):
        """
        Retrieve the name used for a GitLab group that contains all repositories
        for this project on some GitLab service.

        If there are no sources with GitLab tokens for this project, then this
        property returns `None`.
        """

        if self.gitlab_source is None:
            return None

        return self._project_name

    @property
    def gitlab_source(self):
        """
        Retrieve a source providing credentials for a GitLab instance.

        If there is no such source, then this property returns `None`.
        """

        self._load_sources()
        for source in self._sources:
            if 'gitlab_token' in source:
                return source

        return None

    @property
    def quality_metrics_name(self):
        """
        Retrieve the name used in the quality metrics project definition.

        If the project has no long name or if it is a subproject of another
        project, then this property returns `None`.
        """

        if self._project_name is None or self._main_project is not None:
            return None

        return self._project_name

    @property
    def main_project(self):
        """
        Retrieve the main project for this subproject, or `None` if the project
        has no known hierarchical relation with another project.
        """

        return self._main_project

class Sprint_Data(object):
    """
    Object that loads sprint data and allows matching timestamps to sprints
    based on their date ranges.

    Only works after jira_to_json.py has retrieved the sprint data.
    """

    def __init__(self, project):
        self._project = project

        with open(self._project + '/data_sprint.json', 'r') as sprint_file:
            self._data = json.load(sprint_file)

        self._sprint_ids = []
        self._start_dates = []
        self._end_dates = []
        self._date_format = '%Y-%m-%d %H:%M:%S'

        for sprint in self.get_sorted_sprints():
            self._sprint_ids.append(int(sprint['id']))
            self._start_dates.append(self._parse_date(sprint['start_date']))
            self._end_dates.append(self._parse_date(sprint['end_date']))

    def _parse_date(self, date):
        return datetime.strptime(date, self._date_format)

    def get_sorted_sprints(self):
        """
        Retrieve the list of sprints sorted on start date.
        """

        return sorted(self._data, key=lambda sprint: sprint['start_date'])

    def find_sprint(self, time):
        """
        Retrieve a sprint ID of a sprint that encompasses the given datetime
        object `time`. If not such sprint exists, `None` is returned.
        """

        # Find start date
        i = bisect.bisect_left(self._start_dates, time)
        if i == 0:
            # Older than all sprints
            return None

        # Find end date
        if time >= self._end_dates[i-1]:
            # Not actually inside this sprint (either later than the sprint
            # end, or partially overlapping sprints that interfere)
            return None

        return self._sprint_ids[i-1]

def parse_date(date):
    """
    Convert a date string from sources like JIRA to a standard date string,
    excluding milliseconds and using spaces to separate fields instead of 'T'.

    If the date cannot be parsed, '0' is returned.
    """

    date_string = str(date)
    date_string = date_string.replace('T', ' ')
    date_string = date_string.split('.', 1)[0]
    if date_string is None:
        return "0"

    return date_string

def parse_unicode(text):
    """
    Convert unicode `text` to a string without unicode characters.
    """

    if isinstance(text, unicode):
        return text.encode('utf8', 'replace')

    return str(text)
