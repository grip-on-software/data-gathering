from jira import JIRA
import json


# customfield_10404 ->      bugfix
# issueType         ->      type
# project           ->      project_id
# customfield_10209 ->      review_comments
# customfield_10002 ->      storypoint
# customfield_10097 ->      additional_information

def translateFields(diffs):
    fields_translation = {}
    fields_translation['Additional information'] = 'additional_information'
    fields_translation['Review comments'] = 'review_comments'
    fields_translation['Story Points'] = 'storypoint'
    fields_translation['project'] = 'project_id'
    fields_translation['issuetype'] = 'type'
    fields_translation['Bug fix'] = 'bugfix'

    result = {}
    for key, value in diffs.iteritems():
        if key in fields_translation:
            result[fields_translation[key]] = value
        else:
            result[key] = value
    return result

def create_transition(source_data, diffs):
    result=dict(source_data) # Shallow copy, see addendum below
    result.update(diffs)
    return result

def parseDate(date_string):
    string = date_string
    string = string.replace('T', ' ')
    return string.split('.',1)[0]

options = {
    'server': 'https://JIRA_SERVER.localhost/'
}

jira = JIRA(options, basic_auth=('USERNAME', 'PASSWORD'))    # a username/password tuple

overall_data = []

startAt = 0
iterate_size = 20
iterate_max = 100000
issues = jira.search_issues('project=PROJ1',startAt=startAt,maxResults=iterate_size,expand='attachment,changelog', fields='summary,resolutiondate,watches,created,updated,description,duedate,issuetype,customfield_10404,resolution,fixVersions,priority,project,attachment,project,assignee,reporter,customfield_10209,customfield_10002,customfield_10097,status,issuelinks')

developer_data = []
type_data = []
status_data = []
fixVersion_data = []
resolution_data = []
priority_data = []
relationshiptype_data = []
issueLinks = []

while issues and iterate_size <= iterate_max:
    print 'Analyzing ' + str(iterate_size) + ' issues: ' + str(startAt) + ' through ' + str(iterate_size + startAt)
    count = 1

    for issue in issues:
        if hasattr(issue.fields, 'issuelinks') and issue.fields.issuelinks is not None:
            for issuelink in issue.fields.issuelinks:
                if hasattr(issuelink, 'outwardIssue') and hasattr(issuelink, 'type') and hasattr(issuelink.type, 'id'):
                    issueLinks.append({
                        'from_id' : str(issue.id),
                        'to_id' : str(issuelink.outwardIssue.id),
                        'relationshiptype' : issuelink.type.id
                    })

                if hasattr(issuelink, 'inwardIssue') and hasattr(issuelink, 'type') and hasattr(issuelink.type, 'id'):
                    issueLinks.append({
                        'from_id' : str(issue.id),
                        'to_id' : str(issuelink.inwardIssue.id),
                        'relationshiptype' : issuelink.type.id
                    })

    startAt = startAt + iterate_size

    if startAt + iterate_size > iterate_max:
        iterate_size = iterate_max - startAt

    issues = jira.search_issues('project=PROJ1',startAt=startAt,maxResults=iterate_size,expand='attachment,changelog', fields='summary,resolutiondate,watches,created,updated,description,duedate,issuetype,customfield_10404,resolution,fixVersions,priority,project,attachment,project,assignee,reporter,customfield_10209,customfield_10002,customfield_10097,status,issuelinks')


print issueLinks


with open('data_issuelinks.json', 'w') as outfile:
    json.dump(issueLinks, outfile, indent=4)
