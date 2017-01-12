import argparse
import json
from pprint import pprint
import ast
import requests
import gzip
import io
import os
import traceback
from utils import parse_date

project_names = {
    "PROJ1": "project1",
    "PROJ2": "project2",
    "PROJ3": "project3"
}
jenkins_url = "http://www.JENKINS_SERVER.localhost:8080/view/Quality%20reports/job/create-full-history/ws/"

def parse_args():
    parser = argparse.ArgumentParser(description="Obtain and convert a metrics history file in a JSON format readable by the database importer.")
    parser.add_argument("project", help="project key")
    parser.add_argument("--start-from", dest="start_from", type=int, default=None, help="line number to start reading from")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--url", default=jenkins_url, help="url prefix to obtain the file from")
    group.add_argument("--file", help="local file to read from")
    return parser.parse_args()

def read_project_file(data_file, start_from=0):
    metric_data = []
    line_count = 0

    for row in itertools.islice(data_file, start_from, None):
        line_count += 1
        if row.strip() == "":
            continue

        metric_row = ast.literal_eval(row)
        for metric in metric_row:
            if isinstance(metric_row[metric], tuple):
                metric_row_data = {
                    'name': metric,
                    'value': metric_row[metric][0],
                    'category': metric_row[metric][1],
                    'date': parse_date(metric_row[metric][2])
                }
                metric_data.append(metric_row_data)

    print 'Number of lines read: ' + str(line_count)
    print 'Number of new metric values: ' + len(metric_data)
    return metric_data, line_count

def main():
    args = parse_args()
    project_key = args.project
    start_from = args.start_from
    line_filename = project_key + '/history_line_count.txt'
    if start_from is None:
        if os.path.exists(line_filename):
            with open(line_filename, 'r') as f:
                start_from = int(f.read())
        else:
            start_from = 0

    if args.file is not None:
        with open(args.file, 'r') as data_file:
            metric_data, line_count = read_project_file(data_file, start_from)
    else:
        if project_key in project_names:
            project_name = project_names[project_key]
        else:
            print("No metrics history files available for " + project_key + ", skipping.")
            return

        url = args.url + project_name + "/history.json.gz"
        request = requests.get(url)
        stream = io.BytesIO(request.content)
        try:
            data_file = gzip.GzipFile(mode='r', fileobj=stream)
        except:
            traceback.print_exc()
            return

        metric_data, line_count = read_project_file(data_file, start_from)

    with open(project_key + '/data_metrics.json', 'w') as outfile:
        json.dump(metric_data, outfile, indent=4)

    with open(line_filename, 'w') as line_file:
        line_file.write(bytes(start_from + line_count))

if __name__ == "__main__":
    main()
