Software development process data gathering
===========================================

The Python scripts and modules in this repository gather data from different 
sources that are used by software development teams and projects, as well as 
control a distributed setup of data gathering. The "scraper" scripts are part 
of Grip on Software, a research project involving a larger pipeline where the 
gathered data is made available for analysis purposes through a database setup.

Each script reads data from a source based on the requested project and any 
additional parameters (command-line arguments, settings and credentials). 
Formatted data is then exported as a JSON file, which is usually a list of 
objects with properties, according to a defined schema. The exported data is 
suited for import into a MonetDB database.

The modules are able to be deployed in different software development ecosystem 
setups. There are several ways to use the data gathering scripts and modules, 
depending on the situation that they are used in:

- Manually: After installation and configuration, calling the appropriate 
  scripts should provide exported data available for further processing.
- Docker: The installation can be streamlined by using a Docker image.
- Jenkins: Either using the Docker image or a virtual environment, a Jenkins 
  job from a central instance can obtain updated data of projects and provide 
  it to the MonetDB database.
- Agent: A Docker image can be deployed in a separate network to acquire 
  updated data for a limited number of projects, based on frequent intervals 
  with pre-flight checks (a 'Daemon' mode) and send the data to a controller.
- Controller: A central instance can handle pre-flight checks, receive exported 
  data from agents and provide it to the MonetDB database. The controller runs 
  some daemon servers to track agent data and make web interfaces available.
- Module: Certain components of this Python package are usable as a wrapper to 
  check status of certain services, such as Jenkins or Git, in other 
  applications, such as a deployment quality gate.

## Installation

The data gathering scripts and modules require Python version 3.6+. Due to 
dependencies for building the Alpine Linux-based Docker image, Python 3.8 is 
the recommended version; later versions are unsupported.

The scripts have been tested on MacOS 10.14+, Ubuntu 16.04+, CentOS 7.3+ as 
well as on some Windows versions.

The scripts and modules are two separate concepts with regard to installation: 
the data gathering module `gatherer` must be installed so that the scripts can 
always locate the module. Additionally, the scripts and modules have 
dependencies which must be installed. Each of these steps can be done 
separately or in combination with one another:

- Run `pip install -r requirements.txt` to install the dependencies for the 
  data gathering scripts. Next, `pip install -I 'python-gitlab>=1.10.0'` 
  installs a proper version for our data gathering; there will be some warnings 
  about it being incompatible with the outdated Quality-report dependency, but 
  these warnings can be ignored.
  - If you want to gather data from spreadsheets with seat counts, Topdesk or 
    LDAP: run `pip install -r requirements-jenkins.txt`, which also ensures 
    that the normal dependencies are installed.
  - For the controller: run `pip install -r requirements-daemon.txt`, which 
    also ensures that the normal dependencies are installed.
  - For static code analysis: run `pip install -r requirements-analysis.txt`, 
    which installs dependencies for Pylint and mypy (typing extensions) as well 
    as all the other dependencies, even those in Jenkins and controller setups.
- Run `python setup.py install` to install the module and any missing 
  dependencies for the data gathering module. Note that some versions of 
  `setuptools`, which is used in this step, are unable to use wheels or eggs 
  even if they are supported by the platform. Due to the additional compilation 
  time required for some source packages, running both the `pip` and `setup.py` 
  commands may therefore be faster than only `setup.py`.
- Instead of running the `setup.py` script from this repository directly, you 
  can also use `pip install gros-gatherer` to obtain the module. You may need 
  to add additional parameters, such as `--extra-index-url` for a private 
  repository and `--process-dependency-links` to obtain Git dependencies.

We recommend creating a virtual environment to manage the dependencies. Make 
sure that `python` runs the Python version in the virtual environment. Another 
option is to add `--user` to the commands above if you do not have access to 
the system libraries, or do not want to store the libraries in that path. For 
the controller setup, a virtual environment must be created beneath 
`/usr/local/envs` (create this directory) named `controller` with the 
dependencies above. Next, continue with the following steps:

- Configure the agent, controller or development environment using the settings 
  and credentials files as explained in the [configuration](#configuration) 
  section.
- For the controller: use `sudo ./controller/setup.sh` to create services and 
  symlink scripts to make them available for the services.

Some scripts and controller services interact with a database for update 
trackers, project salts and status information storage. This database must be 
a MonetDB instance pre-installed in the environment where the controller is 
able to access it directly.

## Data sources

The following list provides the supported version of platforms that the data 
gatherer can use:

- Jira: Tested with Jira 7.9.2 and later with Agile 7.3.1 and later.
- Version control systems:
  - Git: Tested with Git clients with version 1.8.3 and later. Supported review 
    systems are GitHub, GitLab and Azure DevOps (TFS/VSTS).
    - GitLab: Tested with version 9.4 and later. The legacy API v3 is supported
      up to version 0.0.2 of the gatherer (thus working with GitLab version 8), 
      after which it has been dropped.
    - Azure DevOps: Tested with TFS versions 2015, 2017 and 2018.
  - Subversion: Tested with server version 1.6 and later and client version 1.7 
    and later.
- Quality report: Works with version 2.21 or later.
- Quality Time: Works with rolling (version 0) releases.
- SonarQube: Works with version 7 and later.
- BigBoat: Works with BigBoat version 5.0 and later.

## Overview

The usual pipeline setup runs the scripts in the following order:

- `scraper/retrieve_importer.py`: Retrieve the Java-based importer application 
  that is used to efficiently import the scraped data into the database.
- `scraper/retrieve_metrics_repository.py`: Retrieve or update project 
  definitions and other tools to parse the definitions from repositories.
- `scraper/retrieve_metrics_base_names.py`: Retrieve base name of live metrics
  from quality report metadata.
- `scraper/retrieve_update_trackers.py`: Retrieve update tracker files from 
  a database that is already filled up to a certain period in time, such that 
  the scraper can continue from the indicated checkpoints.
- `scraper/retrieve_dropins.py`: Retrieve dropin files that may be provided for 
  archived projects, containing already-scraped export data.
- `scraper/project_sources.py`: Retrieve source data from project definitions, 
  which is then used for later gathering purposes.
- `scraper/jira_to_json.py`: Retrieve issue changes and metadata from a Jira 
  instance.
- `scraper/environment_sources.py`: Retrieve additional source data from known 
  version control systems, based on the group/namespace/collection in which the 
  already-known repositories live.
- `scraper/git_to_json.py`: Retrieve version information from version control 
  systems (Git or Subversion), possibly including auxiliary information such as 
  GitLab/GitHub project data (commit comments, merge requests) and TFS work 
  item data (also sprints and team members).
- `scraper/metric_options_to_json.py`: Retrieve changes to metric targets from 
  a changelog of the project definitions.
- `scraper/history_to_json.py`: Retrieve the history of measurement values for 
  metrics that are collected in the project, or only output a reference to it.
- `scraper/jenkins_to_json.py`: Retrieve usage statistics from a Jenkins 
  instance.
- `scraper/sonar_to_json.py`: Retrieve additional or historical metrics 
  directly from a SonarQube instance.

These scripts are already streamlined in the `scraper/jenkins.sh` script 
suitable for a Jenkins job, as well as in a number of Docker scripts explained 
in the [Docker](#docker) section. Depending on the environment, the selected 
scripts to run or the files to produce for an importer, some scripts may be 
skipped through these scripts.

Additionally `scraper/topdesk_to_json.py` can be manually run to retrieve 
reservation data related to projects from a CSV dump (see the 
[Topdesk](#topdesk) section), and `scraper/seats_to_json.py` can be manually 
run to retrieve seat counts for projects from a spreadsheet (see the 
[Seats](#seats) section).

There are also a few tools for inspecting data or setting up sources:

- `scraper/hqlib_targets.py`: Extract default metric norms from the outdated 
  Quality report library repository.
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
  information and immediate jobs. See the [scraper web API](#scraper-web-api) 
  for more details.

Finally, the repository contains a controller API and its backend daemons, and 
a deployment interface:

- `controller/auth/`: API endpoints of the controller, at which agents can 
  register themselves, publish health status and logs, or indicate that they 
  have exported their scraped data. See the [controller API](#controller-api) 
  for more details.
- `controller/controller_daemon.py`: Internal daemon for handling agent user 
  creation and permissions of the agent files.
- `controller/gatherer_daemon.py`: Internal daemon for providing update 
  trackers and project salts for use by the agent.
- `controller/exporter_daemon.py` and `controller/export.sh`: Internal daemon 
  for handling agent's collected data to import into the database.

Other files in the repository are mostly used for build process and validation 
of, e.g., code style and output file formats (the `schema/` directory).

## Docker

The data gathering scripts can be run on a centralized machine with the 
appropriate setup (see [Installation](#installation)) or within one or more 
Docker instances which collect (a part of) the data.

First, you must have a (self-signed) SSL certificate for the controller server 
which provides the API endpoints. Place the public certificate in the `certs/` 
directory. Run `docker build -t gros/data-gathering .` to build the Docker 
image. You may wish to use a registry URL before the image name and push the 
image there for distributed deployments.

Next, start the Docker instance based on the container. Use `docker run --name 
gros-data-gathering-agent -v env:/home/agent/env [options]... 
gros/data-gathering` to start the instance using environment variables from 
a file called `env` to set [configuration](#configuration). 

Depending on this configuration, the Docker instance can run in 'Daemon' mode 
or in 'Jenkins' mode. In 'Daemon' mode, the instance periodically checks if it 
should scrape data. Therefore, it should be started in a daemonized form using 
the option `-d`. Set the environment variables `CRON_PERIOD` (required) and 
`BIGBOAT_PERIOD` (optional) to appropriate periodic values (15min, hourly, 
daily) for this purpose. To start a 'Jenkins-style' run, use the environment 
variable `JENKINS_URL=value`, which performs one scrape job immediately and 
terminates.

You can pass environment variables using the Docker parameter `-e`, or with the 
`environment` section of a Docker compose file. Additionally, configuration is 
read from environment files which must be stored in `/home/agent/env` (added 
from the Docker context during `docker build`) or `/home/agent/config/env` (via 
a volume mount `-v`). For example, skip some of the pre-flight checks using 
`PREFLIGHT_ARGS="--no-secrets --no-ssh"` (see all these options from 
`scraper/preflight.py`). Note that you can enter a running docker instance 
using `docker exec -it gros-data-gathering-agent 
/home/agent/scraper/agent/env.sh` which sets up the correct environment to run 
any of the scripts described in the [overview](#overview).

For advanced setups with many configuration variables or volume mounts, it is 
advisable to create a [docker-compose](https://docs.docker.com/compose/) file 
to manage the Docker environment and resulting scraper configuration. Any 
environment variables defined for the container are passed into the 
configuration. During the build, a file called `env` can be added to the build 
context in order to set up environment variables that remain true in all 
instances. For even more versatility, a separate configuration tool can alter 
the configuration and environment files via shared volumes.

More details regarding the specific configuration of the environment within the 
Docker instance can be found in the [environment](#environment) section.

## Scraper agent web API

In the [Docker instance](#docker) of the agent when running the 'Daemon' mode, 
one can make use of a web API to collect status information about the agent and 
immediately start a scrape operation. By default, the web API server runs on 
port 7070. The API uses JSON as an output format. The following endpoints are 
provided:

- `/status`: Check the status of the scrape process. Returns a body containing 
  a JSON object with keys `ok` and `message`. If a scrape is in operation, then 
  a `200` status code is returned and `ok` is set to `true`. Otherwise, a `503` 
  status code is returned and `ok` is set to `false`. `message` provides 
  a human-readable description of the status.
- `/scrape`: Request a scrape operation. This request must be POSTed, otherwise
  a `400` error is returned. If a scrape is in operation, then a `503` error is 
  returned. If the scrape cannot be started, then a `500` error is returned. If 
  the scrape can be started but immediately provides an error code, then 
  a `503` error is returned. Otherwise, a `201` status code is returned with 
  a body containing a JSON object with key `ok` and value `true`.

When any error is returned, then a JSON body is provided with a JSON object 
containing details regarding the error. The object has a key `ok` with the 
value `false`, a key `version` with a JSON object containing names of 
components and libraries as keys and version strings as values, and a key 
`error` with a JSON object containing the following keys and values:

- `status`: The error status code.
- `message`: The message provided with the error.
- `traceback`: If display of tracebacks is enabled, then the error traceback is 
  provided as a string. Otherwise, the value is `null`.

More details on the scraper API are found in the schemas or in the [Swagger 
UI](https://gros.liacs.nl/swagger/?urls.primaryName=Data%20gathering%20scraper%20agent%20API%20%28view%20only%29).

## Controller API

The controller is meant to run on a host that is accessible by the scraper 
agents in order to exchange information with the agents, databases and 
Jenkins-style scrape jobs. Setup of this host requires some extensive 
configuration of directories and users/permissions in order to keep data secure 
during the scrape process while allowing administration of the agent users. The 
`controller` directory provides a few services which play a role in setting up 
all the backend services.

A web API is exposed by the controller API, provided from the `controller/auth` 
directory. The following endpoints exist:

- `access.py`: Check a list of networks to determine if a user should be shown
  exported data from the projects (one, multiple or all of them).
- `agent.py`: Set up an agent to allow access to update trackers and project 
  salts using a SSH key, updating the permissions of relevant directories.
- `encrypt.py`: Use the project salts to provide an encrypted version of 
  a provided piece of text.
- `export.py`: Update status of an agent, start a Jenkins scrape job and import 
  the agent's scrape data into the database.
- `log.py`: Write logging from the agent to a central location for debugging.
- `status.py`: Check if the agent should be allowed to collect new scrape data 
  based on environment conditions (accessibility of services, allowed networks, 
  correct configuration and directory permissions, and a tracker-based timer). 
  If the agent is POSTing data to this endpoint, then instead store status 
  information in a database or other centralized location.
- `version.py`: Check whether a provided version is up to date.

More details on the controller API are found in the schemas or in the [Swagger 
UI](https://gros.liacs.nl/swagger/?urls.primaryName=Data%20gathering%20controller%20API%20%28view%20only%29).

## Configuration

A number of configuration files are used to point the scraper to the correct 
initial source locations and to apply it in a certain secured environment.

Inspect the `settings.cfg.example` and `credentials.cfg.example` files. Both 
files have sections, option names and values, and dollar signs indicate values 
that should be filled in. You can do this by copying the file to the name 
without `.example` at the end and editing it. For Docker builds, the dollar 
signs indicate environment variables that are filled in when starting the 
instance, as explained in the [Docker](#docker) section. Many configuration 
values can also be supplied through arguments to the relevant pipeline scripts 
as shown in their `--help` output.

Some options may have their value set to a falsy value ('false', 'no', 'off', 
'-', '0' or the empty string) to disable a certain feature or to indicate that 
the setting is not used in this environment.

### Settings

- jira (used by `jira_to_json.py`): Jira access settings.
  - `server` (`$JIRA_SERVER`): Base URL of the Jira server used by the 
    projects.
  - `username` (`$JIRA_USER`): Username to log in to Jira with. This may also
    be provided in a credentials section for the instance's network location 
    (domain and optional port).
  - `password` (`$JIRA_PASSWORD`): Password to log in to Jira with. This may 
    also be provided in a credentials section for the instance's network 
    location (domain and optional port).
- definitions (used by `retrieve_metrics_repository.py` and 
  `project_sources.py`): Project definitions source. The settings in this 
  section may be customized per-project by suffixing the option name with 
  a period and the Jira key of the custom project.
  - `source_type` (`$DEFINITIONS_TYPE`): Domain source type used by the project 
    definitions. This may be a version control system that contains the 
    repository of the definitions, e.g., 'subversion' or 'git'.
  - `name` (`$DEFINITIONS_NAME`): The source name of the data storage, to give 
    it a unique name within the sources of the project. The default is
    'quality-report-definition' and it only shows up in update trackers.
  - `url` (`$DEFINITONS_URL`): The HTTP(S) URL from which the data storage can 
    be accessed. VCS URLs can be automatically converted to SSH if the 
    credentials require so.
  - `path` (`$DEFINITIONS_PATH`): The local directory to check out the 
    repository to. May contain a formatter parameter `{}` which is replaced by 
    the project's quality dashboard name.
  - `base` (`$DEFINITIONS_BASE`): The name of the base library/path that is 
    required to parse the project definitions.
  - `base_url` (`$DEFINITIONS_BASE_URL`): The HTTP(S) URL from which the 
    repository containing the base library for parsing project definitions can 
    be accessed. VCS URLs can be converted to SSH.
  - `required_paths` (`$DEFINITIONS_REQUIRED_PATHS`): If non-empty, paths to 
    check out in a sparse checkout of a repository. For paths that do not 
    contain a slash, the quality metrics name is always added to the sparse 
    checkout.
- quality-time (used by `project_sources.py`): Quality Time source for
  project definitions and metrics history.
  - `name` (`$QUALITY_TIME_NAME`): The source name of the Quality Time server, 
    to give it a unique name within the sources of the project. The default is
    'quality-time-definition' and it only shows up in update trackers.
  - `url` (`$QUALITY_TIME_URL`): The HTTP(S) URL from which the Quality Time 
    main landing UI page can be found.
- history (used by `history_to_json.py`): Quality dashboard metrics history 
  dump locations.  The settings in this section may be customized per-project 
  by suffixing the option name with a period and the Jira project key.
  - `url` (`$HISTORY_URL`): The HTTP(S) URL from which the history dump can be 
    accessed, excluding the filename itself. For GitLab repositories, provide 
    the repository URL containing the dump in the root directory or 
    a subdirectory with the project's quality dashboard.
  - `path` (`$HISTORY_PATH`): The local directory where the history dump file 
    can be found or a GitLab repository containing the dump file should be 
    checked out to. May contain a formatter parameter `{}` which is replaced by 
    the project's quality dashboard name; otherwise it is appended 
    automatically. The path does not include the filename.
  - `compression` (`$HISTORY_COMPRESSION`): The compression extension to use
    for the file. This may be added to the filename if it was not provided, and
    determines the file opening method.
  - `filename` (`HISTORY_FILENAME`): The file name of the history file to use.
  - `delete` (`$HISTORY_DELETE`): Whether to delete a local clone of the 
    repository containing the history file before a shallow fetch/clone.
    This option may need to be enabled for Git older than 1.9 which does not
    fully support shallow fetches due to which file updates are not available.
- metrics (used by `retrieve_metrics_base_names.py`): Quality dashboard report
  locations containing metadata for live metrics. Not used for Quality Time.
  - `host` (`$METRICS_HOST`): The HTTP(S) base name from which the metrics data
    can be obtained for projects in subdirectories by their quality metrics
    name. A JSON formatted metrics report file `json/metrics.json` must be 
    available in such a subdirectory.
  - `url` (`$METRICS_URL`): The HTTP(S) URL from which the metrics metadata can
    be obtained. This must be a URL to a metrics metadata formatted JSON file.
- gitlab (used by `init_gitlab.py`): Research GitLab instance where archived 
  repositories can be stored.
  - `url` (`$GITLAB_URL`): Base URL of the GitLab instance.
  - `repo` (`$GITLAB_REPO`): Repository path of this code base.
  - `token` (`$GITLAB_TOKEN`): API token to authenticate with. The user to 
    which this token is associated should have administrative repository 
    creation and user access management rights.
  - `user` (`$GITLAB_USER`): User that should be able to access the repository 
    containing filtered source code.
  - `level` (`$GITLAB_LEVEL`): Access rights to give to the user that accesses 
    the repository containing filtered source code.
- dropins (used by `retrieve_dropins.py`): Storage instance where dropin files 
  can be retrieved from.
  - `type` (`$DROPINS_STORE`): Store type. The only supported type at this 
    moment is 'owncloud', which must have a 'dropins' folder containing dropins 
    further sorted per-project.
  - `url` (`$DROPINS_URL`): Base URL of the data store.
  - `username` (`$DROPINS_USER`): Username to log in to the data store.
  - `password` (`$DROPINS_PASSWORD`): Password to log in to the data store.
- database (used by `retrieve_update_trackers.py` and `retrieve_salts.py`): 
  Credentials to access the MonetDB database with collected data.
  - `username` (`$MONETDB_USER`): The username to authenticate to the database 
    host with.
  - `password` (`$MONETDB_PASSWORD`): The password of the user.
  - `host` (`$MONETDB_HOST`): The hostname of the database.
  - `name` (`$MONETDB_NAME`): The database name.
- ssh (used by various agent scripts and `retrieve_update_trackers.py`): 
  Configuration of the controller server.
  - `username` (`$SSH_USERNAME`): SSH username to log in to the server for 
    transferring files.
  - `host` (`$SSH_HOST`): Hostname of the controller server, used for both SSH 
    access and HTTPS API requests.
  - `cert` (`$SSH_HTTPS_CERT`): Local path to the certificate to verify the 
    server's certificate against.
- importer (used by `retrieve_importer.py`): Location of the importer 
  distribution.
  - `url` (`$IMPORTER_URL`): HTTP(S) URL at which the distribution ZIP file can 
    be accessed.
  - `job` (`$IMPORTER_JOB`): Name of a Jenkins job that holds artifacts for 
    multiple branches. Freestyle or multibranch pipeline jobs are supported.
  - `branch` (`$IMPORTER_BRANCH`): Branch to use to retrieve the artifact from
  - `results` (`$IMPORTER_RESULTS`): Comma-separated list of Jenkins build 
    results that we consider to be stable builds from which we collect new 
    importer distributions.
  - `artifact` (`$IMPORTER_ARTIFACT`): Path to the distribution directory 
    artifact in the job build artifacts.
- bigboat (used by `bigboat_to_json.py`): BigBoat dashboard to monitor with 
  health checks.
  - `host` (`$BIGBOAT_HOST`): Base URL of the BigBoat dashboard.
  - `key` (`$BIGBOAT_KEY`): API key to use on the BigBoat dashboard.
- jenkins (used by `jenkins_to_json.py` and `controller/exporter_daemon.py`): 
  Jenkins instance where jobs can be started.
  - `host` (`$JENKINS_HOST`): Base URL of the Jenkins instance.
  - `username` (`$JENKINS_USERNAME`): Username to log in to the Jenkins 
    instance. Use a falsy value to not authenticate to Jenkins this way. This 
    may also be provided in a credentials section for the instance's network 
    location (domain and optional port).
  - `password` (`$JENKINS_PASSWORD`): Password to log in to the Jenkins 
    instance. Use a falsy value to not authenticate to Jenkins this way. This 
    may also be provided in a credentials section for the instance's network 
    location (domain and optional port).
  - `verify` (`$JENKINS_VERIFY`): SSL certificate verification for the Jenkins 
    instance. This option has no effect is the Jenkins `host` URL does not use 
    HTTPS. Use a falsy value to disable verification, a path name to specify 
    a specific (self-signed) certificate to match against, or any other value 
    to enable secure verification.
  - `scrape` (`$JENKINS_JOB`): Name of the parameterized Jenkins job to start 
    a (partial) scrape.
  - `token` (`$JENKINS_TOKEN`): Custom token to trigger the job remotely when 
    the Jenkins instance has authorization security. This token must be 
    configured in the build job itself.
- sonar (used by `sonar_to_json.py`): SonarQube instance where we can retrieve
  metrics without the use of a quality dashboard definition.
  - `host` (`$SONAR_HOST`): Base URL of the SonarQube instance.
  - `username` (`$SONAR_USERNAME`): Username or access token to log in to the
     SonarQube instance. Use a falsy value to not authenticate to SonarQube.
  - `password` (`$SONAR_PASSWORD`): Password of the user to log in to the
    SonarQube instance. Use a falsy value to not authenticate to SonarQube.
  - `verify` (`$SONAR_VERIFY`): SSL certificate verification for the SonarQube 
    instance. This option has no effect if the SonarQube `host` URL does not 
    use HTTPS. Use a falsy value to disable verification (currently not 
    honored), a path name to specify a specific (self-signed) certificate to 
    match against, or any other value to enable secure verification.
- schedule (used by `controller/gatherer_daemon.py`): Schedule imposed by the 
  controller API status preflight checks to let the agents check whether they 
  should collect data.
  - `days` (`$SCHEDULE_DAYS`): Integer determining the interval in days between
     each collection run by each agent.
  - `drift` (`$SCHEDULE_DRIFT`): Integer determining the maximum number of 
    minutes that the controller may skew the schedule in either direction, thus 
    causing agents to perform their scheduled scrape earlier or later than they 
    all would. Useful if all agents want to perform the scrape at once to 
    reduce load across the network.
- ldap (used by `ldap_to_json.py`): Connection, authentication and query 
  parameters for an LDAP server.
  - `server` (`$LDAP_SERVER`): URL of the LDAP server, including protocol, host 
    and port.
  - `root_dn` (`$LDAP_ROOT_DN`): The base DN to use for all queries.
  - `search_filter` (`$LDAP_SEARCH_FILTER`): Query to find users based on their 
    login name.
  - `manager_dn` (`$LDAP_MANAGER_DN`): Distinguished Name of the manager 
    account which can query the LDAP server.
  - `manager_password` (`$LDAP_MANAGER_PASSWORD`): Password of the manager 
    account which can query the LDAP server.
  - `group_dn` (`$LDAP_GROUP_DN`): Query to find a group of which the user must 
    be a member to be allowed to login.
  - `group_attr` (`$LDAP_GROUP_ATTR`): Attribute in the group that holds group 
    member login names.
  - `display_name` (`$LDAP_DISPLAY_NAME`): Attribute of the user that holds 
    their displayable name (instead of the login name).
- deploy: Bootstrapping for the deployment application and status dashboard.
  - `auth` (`$DEPLOYER_AUTH`): Authentication scheme to use for the service. 
    Accepted values are 'open' (all logins allowed, only in debug environment), 
    'pwd' (/etc/passwd), 'spwd' (/etc/shadow), and 'ldap' (LDAP server).
- projects: A list of Jira project keys and their long names in quality metrics 
  dashboard and repositories. You may add any number of projects here; the 
  pipeline can obtain project definitions only if they have their Jira project
  key here, are not a subproject and have a non-empty long name.
  - `$JIRA_KEY`: Jira project key for the project that is collected by the 
    Docker instance.
  - `$PROJECT_NAME`: Name of the scraped project in the quality dashboard.
- subprojects: Subprojects and their main project.
  - `$SUBPROJECT_KEY`: Jira project key of the subproject.
- teams: GitHub teams and their main project.
  - `$TEAM_NAME`: GitHub slug of the team that manages the repositories 
    relevant to the project.
- support: Jira project key and an indication of whether they are considered to 
  be a support team.
  - `$SUPPORT_TEAM`: Whether the project is considered to be a support team.
- network (used by `controller/auth/status.py`): The networks that are allowed
  to contain agents.
  - `$CONTROLLER_NETWORK`: A comma-separated list of IP networks (a single IP
    address or a CIDR/netmask/hostmask range consisting of an IP address with 
    zeroes for the host bits followed by a slash and the masking operation)
    which are allowed to perform scrape operations for the project.
- access (used by `controller/auth/access.py`): The networks that are allowed 
  to access retrieved data.
  - `$ACCESS_NETWORK`: A comma-separated list of IP networks (a single IP
    address or a CIDR/netmask/hostmask range consisting of an IP address with 
    zeroes for the host bits followed by a slash and the masking operation)
    which are allowed to access the data. 

### Credentials

The credentials file follows a similar section-option-value scheme as the 
settings, but `credentials.cfg.example` contains two sections: the first, whose 
name is `$SOURCE_HOST`, is to be replaced by the hostname of a version control 
system that contains the project repositories. The second section with the 
placeholder name `$DEFINITIONS_HOST`, is the hostname containing project 
definitions, matching the URLs in the `definitions` section of the settings. 
The two sections by default use separate credentials.

These sections may be edited and additional sections may be added for 
project(s) that have more sources, such as multiple VCS hosts, Jenkins hosts or 
Jira hosts. All options may be set to falsy values, e.g., to perform 
unauthenticated access to to disable access to the service completely.

- `env` (`$SOURCE_CREDENTIALS_ENV` and `$DEFINITIONS_CREDENTIALS_ENV`): Name of 
  the environment variable that contains the path to the SSH identity file. 
  This option is only used by Git. The references variable's value must have 
  a valid path to actually succeed in using SSH access. The path may be 
  symbolic, e.g., `~/.ssh/id_rsa`.
- `username` (`$SOURCE_USERNAME` and `$DEFINITIONS_USERNAME`): Username to log 
  in to the version control system. This may differ by protocol used, and as 
  such one may additionally define `username.ssh` and `username.http` which 
  override the default key. For example, with GitLab/GitHub with SSH, this is 
  'git' but it is the username when accessing via HTTP(S).
- `password` (`$SOURCE_PASSWORD` and `$DEFINITIONS_PASSWORD`): Password to log 
  in to the version control system. Ignored if we connect to the version 
  control system using SSH. This happens when `env` is not a falsy value.
- `port` (`$SOURCE_PORT`): Override the port used by the source. This can be 
  used to redirect HTTP(s) or SSH to an alternative port, which may be useful 
  if the source information is stale or if there is a proxy or firewall 
  enforcing the use of a different port. In all normal uses this option is not 
  needed.
- `protocol` (`$SOURCE_PROTOCOL`): Web protocol to use for APIs of custom
  sources like GitLab, GitHub and TFS. This must be either 'http' or 'https' if 
  it is provided. This is only necessary if it differs from the protocol used 
  by the source URLs, such as when you start out with SSH URLs, and even then 
  it is only necessary if the source does not select the appropriate web 
  protocol by default ('http' for GitLab, 'https' for GitHub) and the host is 
  not correctly configured to redirect to the protocol in use.
- `web_port` (`$SOURCE_WEB_PORT`): Web port to use for APIs and human-readable 
  sites of TFS. This is only required if the port is not known from the source 
  URL, such as when you start out with SSH URLs, and the web port is not the 
  default port for the protocol (80 for HTTP and 443 for HTTPS), such as 8080.
  It only works for TFS and is ignored by other source types.
- `github_api_url` (`$SOURCE_GITHUB_API`): URL to the GitHub API. This can 
  usually be set to a falsy value, which falls back to the default GitHub API. 
  You need to set this for GitHub Enterprise when hosted on a custom domain.
- `github_token` (`$SOURCE_GITHUB_TOKEN`): API token for GitHub in order to 
  obtain auxiliary data from GitHub.
- `github_bots` (`$SOURCE_GITHUB_BOTS`): Comma-separated list of GitHub user 
  login names whose comments are excluded from the import of auxiliary data.
- `gitlab_token` (`$SOURCE_GITLAB_TOKEN` and `$DEFINITONS_GITLAB_TOKEN`): API 
  token for GitLab instances in order to obtain auxiliary data from GitLab or 
  interface with its authorization scheme.
- `tfs` (`$SOURCE_TFS`): Set to a non-falsy value to indicate that the source 
  is a Team Foundation Server and thus has auxiliary data aside from the Git 
  repository. If this is true, then any collections found based on the initial
  source that we have are collected, otherwise the value must be a collection
  name starting with `tfs/`. Any projects within or beneath the collection may
  then be gathered.
- `group` (`$SOURCE_GITLAB_GROUP`): The name of the custom GitLab group. Used 
  for group URL updates when the repositories are archived, and for API queries 
  for finding more repositories.
- `from_date` (`$SOURCE_FROM_DATE`): Date from which to start collecting commit 
  revisions during normal scrape operations. This allows for ignoring all 
  commits authored before this date in all repositories on this host, which can 
  be useful for ignoring migration commits. Note that the `tag` option 
  overrides this behavior. Only for Git repositories.
- `tag` (`$SOURCE_TAG`): If the given value is a tag name in a selected Git 
  repository, then only the commits leading to this tag are collected during 
  normal scrape operations. This overrides normal master branch collection and 
  the `from_date` option, and can be useful for scraping a subset of 
  a repository in relation to migration.
- `strip` (`$SOURCE_STRIP`): Strip an initial part of the path of any source
  repository hosted from this host when converting the source HTTP(s) URL to an 
  SSH URL. Useful for GitLab instances hosted behind path-based proxies.
- `unsafe_hosts` (`$SOURCE_UNSAFE`): Disable strict HTTPS certificate and SSH 
  host key verification for the host. This works for Git SSH communication and 
  Subversion HTTPS requests.
- `skip_stats` (`$SOURCE_SKIP_STATS`): Disable collection of statistics on 
  commit sizes from repositories at this source.
- `agile_rest_path` (used by `jira` source type): The REST path to use for Jira 
  Agile requests. Set to `agile` in order to use the public API.

### Environment

When running the scraper agent using [Docker](#docker), as mentioned in that 
section, all settings and credentials may be set through environment variables, 
originating from either Docker parameters (Jenkins-style runs only) or `env` 
files.

The `env` files may exist in the `/home/agent` directory as added during 
a build of the Docker image, as well as in the `/home/agent/config` volume; 
both files are read during startup as well as when starting any scrape 
operation. This writes the variables into the configuration files on the 
`/home/agent/config` volume (only if they do not yet exist) at startup, and 
makes other environment variables available during the scrape.

The following environment variables alter the Docker instance behavior, aside 
from writing them into the configuration files (if at all):

- `$CRON_PERIOD`: The frequency of which the scrape should be attempted, i.e.,
  how often to perform the preflight checks and obtain data from sources if all
  checks pass. The period may be `15min`, `hourly`, `daily`, `weekly` and 
  `monthly`. This enables the 'Daemon' mode of the scraper.
- `$BIGBOAT_PERIOD`: The frequency of which the status information from the
  BigBoat dashboard should be retrieved. This can hold the same values as 
  `$CRON_PERIOD` and only takes effect if 'Daemon' mode is enabled.
- `$JENKINS_URL`: Set to any value (preferably the base URL of the Jenkins
  instance on which the agent runs) to enable the 'Jenkins-style' mode of the
  scraper.
- `$PREFLIGHT_ARGS`: Arguments to pass to the script that performs the 
  preflight checks. This can be used to skip the checks completely. The scraper 
  web API uses this to force a scrape run upon request, but it is otherwise
  honored for both 'Daemon' and 'Jenkins-style' modes.
- `$AGENT_LOGGING`: If provided, then this indicates to the logging mechanism
  that additional arguments and functionality should be provided to upload 
  logging to a logger server on the controller host. Aside from this 
  functionality, the 'Daemon' mode of the agent always uploads the entire log 
  to the controller at the end of the scrape.
- `$JIRA_KEY`: The Jira project key to use for the entire scrape operation. 
  This is required to generate and spread keys to the VCS sources and 
  controller, as well as to actually perform the collection. It may be provided 
  at a later moment than the initial startup.
- `$DEFINITIONS_CREDENTIALS_ENV`: Used during key generation to determine the
  environment variable holding the path to store/obtain the main private key.
- `$SOURCE_HOST` and `$DEFINITIONS_HOST`: Used during key generation to spread
  the public key to, assuming they are GitLab hosts, when the sources have not 
  been located yet.

In addition, the following environment variables change the configuration of 
all the modes in which the data gathering modules are used:

- `$GATHERER_SETTINGS_FILE`: The path to the `settings.cfg` file.
- `$GATHERER_CREDENTIALS_FILE`: The path to the `credentials.cfg` file.
- `$GATHERER_URL_BLACKLIST`: A comma-separated deny list of URL patterns that 
  should not be attempted to connect with. The URL patterns may contain 
  asterisks (`*`) to match any number of characters in that component of the 
  URL (scheme, host or path), other types of patterns are not supported. 
  Sources that are located at matched URLs are not connected by modules, to 
  avoid long timeouts or firewalls.

### Issue trackers (Jira and Azure DevOps)

In order to properly convert fields from different issue trackers, projects 
with custom fields, and preserve semantics between them, two files called 
`jira_fields.json` and `vsts_fields.json` define a mapping for exported issue 
data fields from the internal field names in the issue trackers. The files are 
by default configured to help with common situations found in two organizations 
(ICTU and Wigo4it). Customization of these files may be relevant when another 
organization is used.

In order to validate a (customized) field mapping, the schema files are of use. 
For example, by installing the `check-jsonschema` PyPI package, you can run 
`check-jsonschema --schemafile schema/jira/fields.json jira_fields.json` (Jira) 
or `check-jsonschema--schemafile schema/tfs/fields.json vsts_fields.json` 
(Azure DevOps) to check validity.

### Seats

For `seats_to_json.py`, the presence of a `seats.yml` specification file is 
necessary. The YAML file contains keys and values, which may contain sub-arrays 
and lists. The following keys are necessary:

- `sheet`: The name of the worksheet within the XLS/XLSX workbook that contains
  the seat counts.
- `filename`: Format that valid workbook file names must adhere to. The format 
  must contain `strptime` format codes in order to deduce the time at which the 
  file was created.
- `projects`: A mapping of project names and project keys. The project name 
  should appear in the first worksheet column (excluding the `prefixes`).
  The project keys may be a single Jira project key to map the project name to, 
  or a list of Jira project keys to distribute the seat counts evenly over.
- `prefixes`: A list of strings that should be removed from names in the first 
  worksheet column before using them as a project name.
- `ignore`: A list of strings that indicate that no further projects can be 
  found in the remaining rows when a name in the first worksheet column starts 
  with one of the ignore strings.

### Topdesk

For `topdesk_to_json.py`, the presence of a `topdesk.cfg` configuration file is 
necessary. The `projects` section has option names corresponding to Jira 
project keys and values corresponding to the project representation pass number 
in the CSV dump. The `names` section have internal identifiers for the columns 
in the CSV dump as options, and their associated values are the actual names in 
the CSV dump. The `whitelist` section contains a global allow list under the 
option name `all`, which is a regular expression that matches descriptions of 
items that are relevant events. The section may also have project-specific 
allow list(s), which instead match event descriptions that are specifically 
relevant to the project. The `blacklist` section contains a global deny list 
under the option name `all` that filters irrelevant events based on their 
description. There is no project-specific deny list.

## Testing

Currently, the modules do not come with unit tests, instead depending on the 
correctness of dependencies to provide with accurate data from sources and 
testing the actual system in non-production settings. Plans exist to include 
some unit tests in the future.

The Python scripts and modules conform to code style and typing standards which 
may be checked using Pylint and mypy, respectively, after following the 
[installation](#installation) instructions for static code analysis.

For Pylint:

```
python -m pylint gatherer scraper controller maintenance setup.py --exit-zero \
    --reports=n \
    --msg-template="{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}" \
    -d duplicate-code
```

For mypy:

```
mypy gatherer scraper controller maintenance setup.py \
    --html-report mypy-report --cobertura-xml-report mypy-report \
    --junit-xml mypy-report/junit.xml --no-incremental --show-traceback
```

Finally, the schemas in the `schema/` directory allow validation of certain 
configuration files as well as all the exported artifacts against the schema. 
For example, the Jira and Azure DevOps field mapping specifications are able to 
be checked; see the [issue trackers](#issue-trackers-jira-and-azure-devops) 
section for an example.
