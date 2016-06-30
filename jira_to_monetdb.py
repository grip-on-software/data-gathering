from jira import JIRA
import json
import re


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

def parseDate(date_string):
    string = date_string
    string = string.replace('T', ' ')
    return string.split('.',1)[0]

jira = JIRA(options, basic_auth=('USERNAME', 'PASSWORD'))    # a username/password tuple

overall_data = []

startAt = 0
iterate_size = 50
iterate_max = 100000
issues = jira.search_issues('project=PROJ1',startAt=startAt,maxResults=iterate_size,expand='attachment,changelog', fields='summary,resolutiondate,watches,created,updated,description,duedate,issuetype,customfield_10404,resolution,fixVersions,priority,project,attachment,project,assignee,reporter,customfield_10209,customfield_10002,customfield_10097,status')

count = 1

while issues and iterate_size <= iterate_max:
    print 'Analyzing ' + str(iterate_size) + ' issues: ' + str(startAt) + ' through ' + str(iterate_size + startAt)

    for issue in issues:
        data = {    'issue_id'    : str(issue.id),
                    'key'   : str(issue.key),
                    'resolution_date': parseDate(str(issue.fields.resolutiondate)),
                    'watchers': str(issue.fields.watches.watchCount),
                    'created': parseDate(str(issue.fields.created)),
                    'updated': parseDate(str(issue.fields.updated)),
                }
        issueData = []
        lastIssueData = {}
        if hasattr(issue.fields, 'issuetype') and issue.fields.issuetype is not None and hasattr(issue.fields.issuetype, 'id'):
            data['type'] = str(issue.fields.issuetype.id)
        else:
            data['type'] = 0

        if hasattr(issue.fields, 'customfield_10404') and issue.fields.customfield_10404 is not None and hasattr(issue.fields.customfield_10404, 'id'):
            data['bugfix'] = str(issue.fields.customfield_10404.id)
        else:
            data['bugfix'] = str(0)

        if hasattr(issue.fields, 'resolution') and issue.fields.resolution is not None and hasattr(issue.fields.resolution, 'id'):
            data['resolution'] = str(issue.fields.resolution.id)
        else:
            data['resolution'] = str(0)

        if hasattr(issue.fields, 'fixVersions') and issue.fields.fixVersions is not None and hasattr(issue.fields.fixVersions, 'id'):
            data['fixVersions'] = str(issue.fields.fixVersions.id)
        else:
            data['fixVersions'] = str(0)

        if hasattr(issue.fields, 'priority') and issue.fields.priority is not None and hasattr(issue.fields.priority, 'id'):
            data['priority'] = str(issue.fields.priority.id)
        else:
            data['priority'] = str(0)

        if hasattr(issue.fields, 'project') and issue.fields.project is not None and hasattr(issue.fields.project, 'id'):
            data['project_id'] = str(issue.fields.project.id)
        else:
            data['project_id'] = str(0)

        if hasattr(issue.fields, 'reporter') and issue.fields.reporter is not None and hasattr(issue.fields.reporter, 'name'):
            string_to_encode = issue.fields.reporter.name
            if isinstance(string_to_encode, unicode):
                encoded_string = string_to_encode.encode('utf8','replace')
            else:
                encoded_string = str(string_to_encode)
            data['reporter'] = encoded_string
        else:
            data['reporter'] = str(0)

        if hasattr(issue.fields, 'assignee') and issue.fields.assignee is not None and hasattr(issue.fields.assignee, 'name'):
            string_to_encode = issue.fields.assignee.name
            if isinstance(string_to_encode, unicode):
                encoded_string = string_to_encode.encode('utf8','replace')
            else:
                encoded_string = str(string_to_encode)
            data['assignee'] = encoded_string
        else:
            data['assignee'] = str(0)

        if hasattr(issue.fields, 'status') and issue.fields.status is not None and hasattr(issue.fields.status, 'id'):
            data['status'] = str(issue.fields.status.id)
        else:
            data['status'] = str(0)

        if hasattr(issue.fields, 'description') and issue.fields.description is not None:
            string_to_encode = issue.fields.description
            if isinstance(string_to_encode, unicode):
                encoded_string = string_to_encode.encode('utf8','replace')
            else:
                encoded_string = str(string_to_encode)
            data['description'] = encoded_string
        else:
            data['description'] = str(0)

        if hasattr(issue.fields, 'summary') and issue.fields.summary is not None:
            string_to_encode = issue.fields.summary
            if isinstance(string_to_encode, unicode):
                encoded_string = string_to_encode.encode('utf8','replace')
            else:
                encoded_string = str(string_to_encode)
            data['title'] = encoded_string
        else:
            data['title'] = str(0)

        if hasattr(issue.fields, 'duedate') and issue.fields.duedate is not None:
            string_to_encode = issue.fields.duedate
            if isinstance(string_to_encode, unicode):
                encoded_string = string_to_encode.encode('utf8','replace')
            else:
                encoded_string = str(string_to_encode)
            data['duedate'] = parseDate(encoded_string)
        else:
            data['duedate'] = str(0)

        if hasattr(issue.fields, 'customfield_10209') and issue.fields.customfield_10209 is not None:
            string_to_encode = issue.fields.customfield_10209
            if isinstance(string_to_encode, unicode):
                encoded_string = string_to_encode.encode('utf8','replace')
            else:
                encoded_string = str(string_to_encode)
            data['review_comments'] = encoded_string
        else:
            data['review_comments'] = str(0)

        if hasattr(issue.fields, 'customfield_10002') and issue.fields.customfield_10002 is not None:
            string_to_encode = issue.fields.customfield_10002
            if isinstance(string_to_encode, unicode):
                encoded_string = string_to_encode.encode('utf8','replace')
            else:
                encoded_string = str(string_to_encode)
            data['storypoint'] = encoded_string
        else:
            data['storypoint'] = str(0)

        if hasattr(issue.fields, 'customfield_10097') and issue.fields.customfield_10097 is not None:
            string_to_encode = issue.fields.customfield_10097
            if isinstance(string_to_encode, unicode):
                encoded_string = string_to_encode.encode('utf8','replace')
            else:
                encoded_string = str(string_to_encode)
            data['additional_information'] = encoded_string
        else:
            data['additional_information'] = str(0)

        if hasattr(issue.fields, 'attachment'):
            attach_list = issue.fields.attachment
            id_list = [attach.id for attach in attach_list]
            data['attachment'] = str(len(id_list))
        else:
            data['attachment'] = str(0)


        
        issue_attachment = jira.issue( issue.key, fields='attachment')
        if hasattr(issue_attachment.fields, 'attachment'):
            attach_list = issue_attachment.fields.attachment
            id_list = [attach.id for attach in attach_list]
            data['attachment'] = len(id_list)
        else:
            data['attachment'] = 0
        
        print str(count)
        print
        print
        count += 1
        

        issueData.append(data)
        lastIssueData = data

        changelog = issue.changelog.__dict__
        changelog = changelog[u'histories']

        diffs_dict = {}

        fields_list = ['issuetype', 'status', 'resolution', 'assignee', 'reporter', 'fixVersions', 'priority', 'project', 'Additional information', 'Story Points', 'Review comments', 'Bug fix']

        for changes in changelog:
             created = parseDate(changes.__dict__[u'created'])

             for c in changes.__dict__[u'items']:
                change = c.__dict__
                if str(change[u'field']) in fields_list:
                    string_to_encode = change[u'from']
                    if isinstance(string_to_encode, unicode):
                        encoded_string = string_to_encode.encode('utf8','replace')
                    else:
                        encoded_string = str(string_to_encode)

                    diffs = {str(change[u'field']) : encoded_string }
                    if created not in diffs_dict:
                        diffs_dict[str(created)] = diffs
                    else:
                        diffs_dict[created].update(diffs)

        prev_diffs = {}
        for created in sorted(diffs_dict.keys(), reverse=True):
            diffs = diffs_dict[created]
            diffs = translateFields(diffs)
            if not prev_diffs:
                prev_diffs = diffs
                continue
            prev_diffs['updated'] = created
            tempdata = create_transition(lastIssueData, prev_diffs)
            issueData.append(tempdata)
            lastIssueData = tempdata
            prev_diffs = diffs

        prev_diffs['updated'] = data['created']
        tempdata = create_transition(lastIssueData, prev_diffs)
        issueData.append(tempdata)
        lastIssueData = tempdata

        overall_data = overall_data + issueData

    startAt = startAt + iterate_size

    if startAt + iterate_size > iterate_max:
        iterate_size = iterate_max - startAt

    issues = jira.search_issues('project=PROJ1',startAt=startAt,maxResults=iterate_size,expand='attachment,changelog', fields='summary,resolutiondate,watches,created,updated,description,duedate,issuetype,customfield_10404,resolution,fixVersions,priority,project,attachment,project,assignee,reporter,customfield_10209,customfield_10002,customfield_10097,status')

for row in overall_data:
    print '-------------------- ROW --------------------'
    for y in row:
        print (y,':', row[y])



with open('data.json', 'w') as outfile:
    json.dump(overall_data, outfile, indent=4)





