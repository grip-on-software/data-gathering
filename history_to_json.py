import argparse
import json
from pprint import pprint
import ast
import requests
import gzip
import io
import traceback

project_names = {
    "PROJ1": "project1",
    "PROJ2": "project2",
    "PROJ3": "project3"
}
jenkins_url = "http://www.JENKINS_SERVER.localhost:8080/view/Quality%20reports/job/create-full-history/ws/"

def parse_args():
    parser = argparse.ArgumentParser(description="Obtain and convert a history file in a JSON format readable by the database importer.")
    parser.add_argument("project", help="project key")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--url", default=jenkins_url, help="url prefix to obtain the file from")
    group.add_argument("--file", help="local file to read from")
    return parser.parse_args()

def parseDate(date_string):
    string = date_string
    string = string.replace('T', ' ')
    string = string.split('.',1)[0]
    if string == None:
        return "0"
    else:
        return string

def read_project_file(data_file):
    metric_data = []
    count = 0

    for row in data_file:
        if row.strip() == "":
            continue

        metric_row = ast.literal_eval(row)
        for metric in metric_row:
            if isinstance(metric_row[metric], tuple):
                metric_row_data = {
                    'name' : metric,
                    'value' : metric_row[metric][0],
                    'category' : metric_row[metric][1],
                    'date' : parseDate(metric_row[metric][2])
                }
                metric_data.append(metric_row_data)
                count += 1

    print 'Number of rows: ' + str(count)
    return metric_data

def main():
    args = parse_args()
    project_key = args.project
    if args.file is not None:
        with open(args.file, 'r') as data_file:
            metric_data = read_project_file(data_file)
    else:
        if project_key in project_names:
            project_name = project_names[project_key]
        else:
            print("No metrics history files available for " + project_key + ", skipping.")
            return

        url = args.url + project_name + "/history.json.gz"
        request = requests.get(url)
        try:
            metric_data = read_project_file(gzip.GzipFile(mode="r", fileobj=io.BytesIO(request.content)))
        except e:
            traceback.print_exc()
            return

    with open(project_key + '/data_metrics.json', 'w') as outfile:
        json.dump(metric_data, outfile, indent=4)

if __name__ == "__main__":
    main()
