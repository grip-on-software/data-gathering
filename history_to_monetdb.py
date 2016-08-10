import json
from pprint import pprint
import ast


def parseDate(date_string):
    string = date_string
    string = string.replace('T', ' ')
    string = string.split('.',1)[0]
    if string == None:
        return "0"
    else:
        return string

metric_data = []
with open('history.json') as data_file:
	count = 0
	for row in data_file:
		metric_row = ast.literal_eval(row)
		for metric in metric_row:
			if isinstance(metric_row[metric], tuple):
				metric_row_data = {'name' : metric, 'value' : metric_row[metric][0], 'date' : parseDate(metric_row[metric][2])}
				metric_data.append(metric_row_data)
			count += 1

	print 'Number of rows: ' + str(count)


with open('data_metrics.json', 'w') as outfile:
    json.dump(metric_data, outfile, indent=4)