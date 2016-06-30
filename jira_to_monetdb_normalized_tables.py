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
    """Returns a copy of source_dict, updated with the new key-value
       pairs in diffs."""
    result=dict(source_data) # Shallow copy, see addendum below
    result.update(diffs)
    return result

options = {
    'server': 'https://JIRA_SERVER.localhost/'
}

jira = JIRA(options, basic_auth=('USERNAME', 'PASSWORD'))    # a username/password tuple

overall_data = []

startAt = 0
iterate_size = 20
iterate_max = 200
issues = jira.search_issues('project=PROJ1&key=PROJ-1234',startAt=startAt,maxResults=iterate_size,expand='attachment,changelog', fields='summary,resolutiondate,watches,created,updated,description,duedate,issuetype,customfield_10404,resolution,fixVersions,priority,project,attachment,project,assignee,reporter,customfield_10209,customfield_10002,customfield_10097,status')

developer_data = []
type_data = []
status_data = []
fixVersion_data = []
resolution_data = []
priority_data = []
relationshiptype_data = []


while issues and iterate_size <= iterate_max:
    print 'Analyzing ' + str(iterate_size) + ' issues: ' + str(startAt) + ' through ' + str(iterate_size + startAt)
    count = 1

    for issue in issues:
        print issue.fields.fixVersions
        '''
        if hasattr(issue.fields, 'issuetype') and issue.fields.issuetype is not None and hasattr(issue.fields.issuetype, 'id'):
            if not any(d.get('id', None) == str(issue.fields.issuetype.id) for d in type_data) and hasattr(issue.fields.issuetype, 'name') and hasattr(issue.fields.issuetype, 'description'):
                type_data.append({
                                'id' : str(issue.fields.issuetype.id), 
                                'name' : str(issue.fields.issuetype.name),
                                'description' : str(issue.fields.issuetype.description)
                                })

        if hasattr(issue.fields, 'status') and issue.fields.status is not None and hasattr(issue.fields.status, 'id'):
            if not any(d.get('id', None) == str(issue.fields.status.id) for d in status_data) and hasattr(issue.fields.status, 'name') and hasattr(issue.fields.status, 'description'):
                status_data.append({
                                'id' : str(issue.fields.status.id), 
                                'name' : str(issue.fields.status.name),
                                'description' : str(issue.fields.status.description)
                                })
        '''
        if hasattr(issue.fields, 'fixVersions') and issue.fields.fixVersions is not None:
            for fixVersion in issue.fields.fixVersions:
                if hasattr(fixVersion, 'id'):
                    if not any(d.get('id', None) == str(fixVersion.id) for d in fixVersion_data) and hasattr(fixVersion, 'name') and hasattr(fixVersion, 'description') and hasattr(fixVersion, 'released'):
                        if hasattr(fixVersion, 'releaseDate'):
                            release_date = parseDate(str(fixVersion.releaseDate))
                            fixVersion_data.append({
                                        'id' : str(fixVersion.id), 
                                        'name' : str(fixVersion.name),
                                        'description' : str(fixVersion.description),
                                        'release_date' : str(release_date)
                                        })
        '''
        if hasattr(issue.fields, 'priority') and issue.fields.priority is not None and hasattr(issue.fields.priority, 'id'):
            if not any(d.get('id', None) == str(issue.fields.priority.id) for d in priority_data) and hasattr(issue.fields.priority, 'name'):
                priority_data.append({
                                'id' : str(issue.fields.priority.id), 
                                'name' : str(issue.fields.priority.name),
                                })
        '''
        if hasattr(issue.fields, 'issueLinks') and issue.fields.issueLinks is not None:
            print 'Links: ' + str(issue.fields.issueLinks.__dict__)
            if hasattr(issue.fields.issueLinks, 'type') and hasattr(issue.fields.issueLinks.type, 'id'):
                if not any(d.get('id', None) == str(issue.fields.issueLinks.type.id) for d in relationshiptype_data) and hasattr(issue.fields.issueLinks.type, 'name'):
                    relationshiptype_data.append({
                                    'id' : str(issue.fields.issueLinks.type.id), 
                                    'name' : str(issue.fields.issueLinks.type.name),
                                    })
        '''
        if hasattr(issue.fields, 'resolution') and issue.fields.resolution is not None and hasattr(issue.fields.resolution, 'id'):
            if not any(d.get('id', None) == str(issue.fields.resolution.id) for d in resolution_data) and hasattr(issue.fields.resolution, 'name') and hasattr(issue.fields.resolution, 'description'):
                resolution_data.append({
                                'id' : str(issue.fields.resolution.id), 
                                'name' : str(issue.fields.resolution.name),
                                'description' : str(issue.fields.resolution.description)
                                })
        '''

    startAt = startAt + iterate_size

    if startAt + iterate_size > iterate_max:
        iterate_size = iterate_max - startAt

    issues = jira.search_issues('project=PROJ1',startAt=startAt,maxResults=iterate_size,expand='attachment,changelog', fields='summary,resolutiondate,watches,created,updated,description,duedate,issuetype,customfield_10404,resolution,fixVersions,priority,project,attachment,project,assignee,reporter,customfield_10209,customfield_10002,customfield_10097,status')
'''
print developer_data
print
print
print
print type_data
print
print
print
print status_data
print
print
print
'''
print fixVersion_data
'''
print
print
print
print resolution_data
print
print
print
print priority_data
'''
print
print
print
print relationshiptype_data

'''
with open('data_type.json', 'w') as outfile:
    json.dump(type_data, outfile, indent=4)

with open('data_status.json', 'w') as outfile:
    json.dump(status_data, outfile, indent=4)
'''

with open('data_fixVersion.json', 'w') as outfile:
    json.dump(fixVersion_data, outfile, indent=4)
'''
with open('data_resolution.json', 'w') as outfile:
    json.dump(resolution_data, outfile, indent=4)

with open('data_priority.json', 'w') as outfile:
    json.dump(priority_data, outfile, indent=4)
'''
with open('data_relationshiptype.json', 'w') as outfile:
    json.dump(relationshiptype_data, outfile, indent=4)
