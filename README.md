Software development process data gathering
===========================================

The scripts and modules in this repository gather data from different sources 
that are used by software development teams and projects. The scripts are part 
of a larger pipeline where the gathered data is made available for analysis 
purposes through a database setup.

The scripts read data from a source based on the requested project and any 
additional parameters (command-line arguments, settings and credentials). 
Formatted data is then exported as a JSON file, which is usually a list of 
objects with properties.

## Installation

The data gathering scripts require Python version 2.7.x or 3.6+.

Run `pip install -r requirements.txt` to install the dependencies. Add `--user` 
if you do not have access to the system libraries, or do not want to store the 
libraries in that path but in your home directory. Additionally, if you want to 
gather Topdesk data, then run `pip install [--user] regex`.

## Overview

The usual pipeline setup runs the scripts in the following order:

- `project_sources.py`: Retrieve source data from project definitions, which is 
  then used for later version control gathering purposes.
- `jira_to_json.py`: Retrieve issue changes and metadata from a JIRA instance.
- `gitlab_sources.py`: Retrieve addition source data from a GitLab instance, 
  based on the group in which the repositories live.
- `git_to_json.py`: Retrieve version information from Git or Subversion 
  instances, possibly including additional information such as GitLab project 
  data (commit comments, merge requests).
- `history_to_json.py`: Retrieve a history file containing measurement values 
  for metrics during the project, or only output a reference to it.
- `metric_options_to_json.py`: Retrieve changes to metric targets from 
  a Subversion repository holding the project definitions.
