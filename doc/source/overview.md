# Repository overview

The usual pipeline setup runs the scripts in the following order:

- `scraper/retrieve_importer.py`: Retrieve the Java-based importer application 
  that is used to efficiently import the scraped data into the database.
- `scraper/retrieve_update_trackers.py`: Retrieve update tracker files from 
  a database that is already filled up to a certain period in time, such that 
  the scraper can continue from the indicated checkpoints.
- `scraper/retrieve_dropins.py`: Retrieve dropin files that may be provided for 
  archived projects, containing already-scraped export data.
- `scraper/project_sources.py`: Retrieve source data from project definitions 
  in Quality-time, which is then used for later gathering purposes.
- `scraper/jira_to_json.py`: Retrieve issue changes and metadata from a Jira 
  instance.
- `scraper/environment_sources.py`: Retrieve additional source data from known 
  version control systems, based on the group/namespace/collection in which the 
  already-known repositories live.
- `scraper/git_to_json.py`: Retrieve version information from version control 
  systems (Git or Subversion), possibly including auxiliary information such as 
  GitLab or GitHub project data (such as commit comments and merge requests) 
  and Azure DevOps/VSTS/TFS work item data (also sprints and team members).
- `scraper/metric_options_to_json.py`: Retrieve changes to metric targets from 
  a changelog of the project definitions as well as the default metric targets.
- `scraper/history_to_json.py`: Retrieve the history of measurement values for 
  metrics that are collected in the project, or only output a reference to it.
- `scraper/jenkins_to_json.py`: Retrieve usage statistics from a Jenkins 
  instance.

These scripts are already streamlined in the `scraper/jenkins.sh` script 
suitable for a Jenkins job, as well as in a number of Docker scripts explained 
in the [Docker](docker.md) section. Depending on the environment, the selected 
scripts to run or the files to produce for an importer, some scripts may be 
skipped through these scripts.

Additionally, `scraper/topdesk_to_json.py` can be manually run to retrieve 
reservation data related to projects from a CSV dump (see the 
[Topdesk](configuration.md#topdesk) section), and `scraper/seats_to_json.py` 
can be manually run to retrieve seat counts for projects from a spreadsheet 
(see the [Seats](configuration.md#seats) section).

There are also a few tools for inspecting data or setting up sources:

- `maintenance/import_bigboat_status.py`: Import line-delimited JSON status 
  information dumps into a database.
- `maintenance/init_gitlab.py`: Set up repositories for filtered or archived 
  source code.
- `maintenance/retrieve_salts.py`: Retrieve project salts from the database.
- `maintenance/update_jira_mails.py`: Update email addresses in legacy dropin 
  developer data from Jira.
- `maintenance/filter-sourcecode.sh`: Retrieve and filter source code 
  repositories of a project so that it is unintelligible but can still be used 
  for code size metrics.

All of these scripts and tools make use of the `gatherer` library, contained 
within this repository, which supplies abstracted and standardized access to 
data sources as well as data storage.

This repository also contains agent-only tools, including Shell-based Docker 
initialization scripts:

- `scraper/agent/init.sh`: Entry point which sets up periodic scraping, 
  permissions and the server.
- `scraper/agent/start.sh`: Prepare the environment for running scripts.
- `scraper/agent/run.sh`: Start a custom pipeline which collects data from 
  the version control systems, exporting it to the controller server.

Aside from the normal data gathering pipeline, an agent additionally uses the 
following scripts to retrieve data or publish status:

- `scraper/bigboat_to_json.py`: Request the status of a BigBoat dashboard and 
  publish this data to the controller server via its API.
- `scraper/generate_key.py`: Generate a public-private key pair and distribute 
  the public part to supporting sources (version control systems) and the 
  controller server, for registration purposes.
- `scraper/preflight.py`: Perform status checks, including integrity of secrets 
  and the controller server, before collecting and exporting data.
- `scraper/export_files.py`: Upload exported data and update trackers via SSH 
  to the controller server and the API for a status indication.
- `scraper/agent/scraper.py`: Web API server providing scraper status 
  information and immediate job scheduling. For more details, see the 
  documentation on the [scraper web API](api.md#scraper-agent-web-api).

Finally, the repository contains a controller API and its backend daemons, and 
a deployment interface:

- `controller/auth/`: API endpoints of the controller, at which agents can 
  register themselves, publish health status and logs, or indicate that they 
  have exported their scraped data. For more details on these endpoints, see 
  the documentation on the [controller API](api.md#controller-api).
- `controller/controller_daemon.py`: Internal daemon for handling agent user 
  creation and permissions of the agent files.
- `controller/gatherer_daemon.py`: Internal daemon for providing update 
  trackers and project salts for use by the agent.
- `controller/exporter_daemon.py` and `controller/export.sh`: Internal daemon 
  for handling agent's collected data to import into the database.

Other files in the repository are mostly used for build process and validation 
of, e.g., code style and output file formats (the `schema/` directory). These 
are described in the [data schemas](https://gros.liacs.nl/schema/) 
documentation.
