from jira import JIRA
import json
import re
import os.path
import sys
############################################
################## SETTINGS ################
############################################
jira_project_key = 'PROJ1'
jira_username = 'USERNAME'
jira_password = 'PASSWORD'
############################################
############################################

try:
	if sys.argv[1] is not None:
		jira_project_key = sys.argv[1]
		data_folder = jira_project_key
except IndexError:
	#no argument given
	data_folder = jira_project_key
print jira_project_key
sys.exit()

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
	string = string.split('.',1)[0]
	if string == None:
		return "0"
	else:
		return string

def parseSprintString(sprint_string):
	sprint_data = {}
	sprint = sprint_string
 	sprint = sprint[sprint.rindex('[')+1:-1]
 	sprint = sprint.split(',')
 	for s in sprint:
 		try:
 			s = s.split('=')
	 		a = s[0].encode('utf-8')
	 		b = s[1].encode('utf-8')
	 		if a == 'endDate' or a == 'startDate':
 				b = parseDate(b)
 			sprint_data[a]= b
		except IndexError:
 			return False
 	return sprint_data

jira = JIRA(options, basic_auth=(jira_username, jira_password))    # a username/password tuple

overall_data = []

startAt = 0
iterate_size = 100
iterate_max = 100000

if not os.path.exists(data_folder):
	os.makedirs(data_folder)

issues = jira.search_issues('project='+jira_project_key,startAt=startAt,maxResults=iterate_size,expand='attachment,changelog', fields='summary,resolutiondate,watches,created,updated,description,duedate,issuetype,customfield_10404,resolution,fixVersions,priority,project,attachment,project,assignee,reporter,customfield_10209,customfield_10002,customfield_10097,customfield_10207,status,issuelinks')

count = 1

developer_data = []
type_data = []
status_data = []
fixVersion_data = []
sprint_data = []
resolution_data = []
priority_data = []
relationshiptype_data = []
issueLinks = []

while issues and iterate_size <= iterate_max:
	print 'Analyzing ' + str(iterate_size) + ' issues: ' + str(startAt) + ' through ' + str(iterate_size + startAt)
	for issue in issues:
		#START collect issue data
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

		if hasattr(issue.fields, 'customfield_10207') and issue.fields.customfield_10207 is not None:
 			
			sprint = issue.fields.customfield_10207[0]
			sprint = parseSprintString(sprint)
			if (sprint is not False):
				string_to_encode = sprint['id']
				if isinstance(string_to_encode, unicode):
					encoded_string = string_to_encode.encode('utf8','replace')
				else:
					encoded_string = str(string_to_encode)
				data['sprint'] = encoded_string

				if not any(d.get('id', None) == str(sprint['id']) for d in sprint_data):
					sprint_data.append({
									'id' : str(sprint['id']), 
									'name' : str(sprint['name']),
									'start_date' : str(sprint['startDate']),
									'end_date' : str(sprint['endDate'])
									})
			else:
				data['sprint'] = str(0)
		else:
			data['sprint'] = str(0)

		if hasattr(issue.fields, 'customfield_10002') and issue.fields.customfield_10002 is not None:
			string_to_encode = issue.fields.customfield_10002
			if isinstance(string_to_encode, unicode):
				encoded_string = string_to_encode.encode('utf8','replace')
				head, sep, tail = encoded_string.partition('.')
			else:
				encoded_string = str(string_to_encode)
				head, sep, tail = encoded_string.partition('.')
			data['storypoint'] = str(int(head))
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
			data['attachment'] = str(len(id_list))
		else:
			data['attachment'] = str(0)
		
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

		#END collect issue data


		#START get normalized table data

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

		if hasattr(issue.fields, 'fixVersions') and issue.fields.fixVersions is not None:
			for fixVersion in issue.fields.fixVersions:
				if hasattr(fixVersion, 'id'):
					if not any(d.get('id', None) == str(fixVersion.id) for d in fixVersion_data) and hasattr(fixVersion, 'name') and hasattr(fixVersion, 'description') and hasattr(fixVersion, 'released'):
						if fixVersion.released == False:
							fixVersion_data.append({
										'id' : str(fixVersion.id), 
										'name' : str(fixVersion.name),
										'description' : str(fixVersion.description),
										'release_date' : str(0)
										})
						elif hasattr(fixVersion, 'releaseDate'):
							release_date = parseDate(str(fixVersion.releaseDate))
							fixVersion_data.append({
										'id' : str(fixVersion.id), 
										'name' : str(fixVersion.name),
										'description' : str(fixVersion.description),
										'release_date' : str(release_date)
										})

		if hasattr(issue.fields, 'priority') and issue.fields.priority is not None and hasattr(issue.fields.priority, 'id'):
			if not any(d.get('id', None) == str(issue.fields.priority.id) for d in priority_data) and hasattr(issue.fields.priority, 'name'):
				priority_data.append({
								'id' : str(issue.fields.priority.id), 
								'name' : str(issue.fields.priority.name),
								})

		if hasattr(issue.fields, 'issuelinks') and issue.fields.issuelinks is not None:
			for issuelink in issue.fields.issuelinks:
				if hasattr(issuelink, 'type') and hasattr(issuelink.type, 'id'):
					if not any(d.get('id', None) == str(issuelink.type.id) for d in relationshiptype_data) and hasattr(issuelink.type, 'name'):
						relationshiptype_data.append({
										'id' : str(issuelink.type.id), 
										'name' : str(issuelink.type.name),
										})

		if hasattr(issue.fields, 'resolution') and issue.fields.resolution is not None and hasattr(issue.fields.resolution, 'id'):
			if not any(d.get('id', None) == str(issue.fields.resolution.id) for d in resolution_data) and hasattr(issue.fields.resolution, 'name') and hasattr(issue.fields.resolution, 'description'):
				resolution_data.append({
								'id' : str(issue.fields.resolution.id), 
								'name' : str(issue.fields.resolution.name),
								'description' : str(issue.fields.resolution.description)
								})

		if hasattr(issue.fields, 'reporter') and issue.fields.reporter is not None and hasattr(issue.fields.reporter, 'name'):
			if not any(d.get('name', None) == str(issue.fields.reporter.name) for d in developer_data) and hasattr(issue.fields.reporter, 'name') and hasattr(issue.fields.reporter, 'displayName'):
				string_to_encode = issue.fields.reporter.displayName
				if isinstance(string_to_encode, unicode):
					encoded_string = string_to_encode.encode('utf8','replace')
				else:
					encoded_string = str(string_to_encode)
				developer_data.append({
								'name' : str(issue.fields.reporter.name),
								'display_name' : encoded_string
								})

		if hasattr(issue.fields, 'assignee') and issue.fields.assignee is not None and hasattr(issue.fields.assignee, 'name'):
			if not any(d.get('name', None) == str(issue.fields.assignee.name) for d in developer_data) and hasattr(issue.fields.assignee, 'name') and hasattr(issue.fields.assignee, 'displayName'):
				string_to_encode = issue.fields.assignee.displayName
				if isinstance(string_to_encode, unicode):
					encoded_string = string_to_encode.encode('utf8','replace')
				else:
					encoded_string = str(string_to_encode)
				developer_data.append({
								'name' : str(issue.fields.assignee.name),
								'display_name' : encoded_string
								})

		#END get normalized table data

		#START get issueLinks

		if hasattr(issue.fields, 'issuelinks') and issue.fields.issuelinks is not None:
			for issuelink in issue.fields.issuelinks:
				if hasattr(issuelink, 'outwardIssue') and hasattr(issuelink, 'type') and hasattr(issuelink.type, 'id'):
					#filter duplicate issuelink
					if not any(d.get('from_id', None) == str(issue.id) and d.get('to_id', None) == str(issuelink.outwardIssue.id) and d.get('relationshiptype', None) == str(issuelink.type.id) for d in issueLinks):
						issueLinks.append({
							'from_id' : str(issue.id),
							'to_id' : str(issuelink.outwardIssue.id),
							'relationshiptype' : issuelink.type.id
						})

				if hasattr(issuelink, 'inwardIssue') and hasattr(issuelink, 'type') and hasattr(issuelink.type, 'id'):
					#filter duplicate issuelink
					if not any(d.get('from_id', None) == str(issue.id) and d.get('to_id', None) == str(issuelink.inwardIssue.id) and d.get('relationshiptype', None) == str(issuelink.type.id) for d in issueLinks):
						issueLinks.append({
							'from_id' : str(issue.id),
							'to_id' : str(issuelink.inwardIssue.id),
							'relationshiptype' : issuelink.type.id
						})

		#END get issueLinks



	startAt = startAt + iterate_size

	if startAt + iterate_size > iterate_max:
		iterate_size = iterate_max - startAt

	issues = jira.search_issues('project='+jira_project_key,startAt=startAt,maxResults=iterate_size,expand='attachment,changelog', fields='summary,resolutiondate,watches,created,updated,description,duedate,issuetype,customfield_10404,resolution,fixVersions,priority,project,attachment,project,assignee,reporter,customfield_10209,customfield_10002,customfield_10097,customfield_10207,status,issuelinks')

print count

#START dump data

with open(data_folder+'/data.json', 'w') as outfile:
	json.dump(overall_data, outfile, indent=4)

with open(data_folder+'/data_type.json', 'w') as outfile:
	json.dump(type_data, outfile, indent=4)

with open(data_folder+'/data_status.json', 'w') as outfile:
	json.dump(status_data, outfile, indent=4)

with open(data_folder+'/data_fixVersion.json', 'w') as outfile:
	json.dump(fixVersion_data, outfile, indent=4)

with open(data_folder+'/data_sprint.json', 'w') as outfile:
	json.dump(sprint_data, outfile, indent=4)

with open(data_folder+'/data_resolution.json', 'w') as outfile:
	json.dump(resolution_data, outfile, indent=4)

with open(data_folder+'/data_priority.json', 'w') as outfile:
	json.dump(priority_data, outfile, indent=4)

with open(data_folder+'/data_relationshiptype.json', 'w') as outfile:
	json.dump(relationshiptype_data, outfile, indent=4)

with open(data_folder+'/data_issuelinks.json', 'w') as outfile:
	json.dump(issueLinks, outfile, indent=4)

with open(data_folder+'/data_developer.json', 'w') as outfile:
	json.dump(developer_data, outfile, indent=4)

#END dump data



