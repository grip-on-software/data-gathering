import bisect
import json
from datetime import datetime

class Sprint_Data(object):
    """
    Object that loads sprint data and allows matching timestamps to sprints
    based on their date ranges.

    Only works after jira_to_json.py has retrieved 
    """

    def __init__(self, project):
        self.project = project

        with open(self.project + '/data_sprint.json', 'r') as f:
            self.data = json.load(f)

        self.sprint_ids = []
        self.start_dates = []
        self.end_dates = []
        self.date_format = '%Y-%m-%d %H:%M:%S'
        for sprint in sorted(self.data, key=lambda sprint: sprint['start_date']):
            self.sprint_ids.append(int(sprint['id']))
            self.start_dates.append(datetime.strptime(sprint['start_date'], self.date_format))
            self.end_dates.append(datetime.strptime(sprint['end_date'], self.date_format))

    def find_sprint(self, time):
        # Find start date
        i = bisect.bisect_left(self.start_dates, time)
        if i == 0:
            # Older than all sprints
            return None
        
        # Find end date
        if time >= self.end_dates[i-1]:
            # Not actually inside this sprint (either later than the sprint 
            # end, or partially overlapping sprints that interfere)
            return None

        return self.sprint_ids[i-1]

def parse_date(date):
    date_string = str(date)
    date_string = date_string.replace('T', ' ')
    date_string = date_string.split('.', 1)[0]
    if date_string is None:
        return "0"
    
    return date_string

def parse_unicode(text):
    if isinstance(text, unicode):
        return text.encode('utf8', 'replace')

    return str(text)
