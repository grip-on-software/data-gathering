Software development process data gathering
===========================================

The scripts and modules in this repository gather data from different sources 
that are used by software development teams and projects, as well as control 
a distributed setup of data gathering. The scripts are part of a larger 
pipeline where the gathered data is made available for analysis purposes 
through a database setup.

The scripts read data from a source based on the requested project and any 
additional parameters (command-line arguments, settings and credentials). 
Formatted data is then exported as a JSON file, which is usually a list of 
objects with properties.

## Installation

The data gathering scripts require Python version 2.7.x or 3.6+. Certain 
webservice daemons only work on Python 2.7.x due to dependencies.

Run `pip install -r requirements.txt` to install the dependencies for the data 
gathering scripts. Add `--user` if you do not have access to the system 
libraries, or do not want to store the libraries in that path but in your home 
directory. Additionally, if you want to gather Topdesk data, then run `pip 
install [--user] regex` (which is not installed by default because it requires 
compilation on Linux hosts).

For the webservice daemons, run `pip install -r requirements-daemon.txt`, which 
also installs the normal dependencies.

## Overview

The usual pipeline setup runs the scripts in the following order:

- `retrieve_importer.py`: Retrieve the Java-based importer application that is 
  used to efficiently import the scraped data into the database.
- `retrieve_metrics_repository.py`: Retrieve or update project definitions and 
  other tools to parse the definitions from repositories.
- `retrieve_update_trackers.py`: Retrieve update tracker files from a database 
  that is already filled up to a certain period in time, such that the scraper 
  can continue from the indicated checkpoints.
- `retrieve_dropins.py`: Retrieve dropin files that may be provided for 
  archived projects, containing already-scraped export data.
- `project_sources.py`: Retrieve source data from project definitions, which is 
  then used for later version control gathering purposes.
- `jira_to_json.py`: Retrieve issue changes and metadata from a JIRA instance.
- `environment_sources.py`: Retrieve additional source data from known version 
  control systems, based on the group/namespace/collection in which the 
  repositories that were found earlier live.
- `git_to_json.py`: Retrieve version information from Git or Subversion 
  instances, possibly including additional information such as GitLab project 
  data (commit comments, merge requests).
- `history_to_json.py`: Retrieve a history file containing measurement values 
  for metrics during the project, or only output a reference to it.
- `metric_options_to_json.py`: Retrieve changes to metric targets from 
  a Subversion repository holding the project definitions.
- `jenkins_to_json.py`: Retrieve usage statistics from a Jenkins instance.

These scripts are already streamlined in the `jenkins-scraper.sh` script 
suitable for a Jenkins job, as well as in a number of Docker scripts explained 
in the [Docker](#docker) section.

Additionally `topdesk_to_json.py` can be manually run to retrieve reservation 
data related to projects from a CSV dump.

There are also a few tools for inspecting data or setting up sources:

- `gitlab_events.py`: Create a dropin dump for events on a GitLab instance.
- `hqlib_targets.py`: Extract default metric norms from the quality reporting 
  library repository.
- `init_gitlab.py`: Set up repositories for filtered or archived source code.
- `retrieve_salts.py`: Retrieve project salts from the database.
- `update_jira_mails.py`: Update email addresses in legacy dropin developer 
  data from JIRA.

All of these scripts and tools make use of the `gatherer` library, contained 
within this repository, which supplies abstracted and standardized access and 
data storage OOP classes with various functionality.

This repository also contains agent-only tools:

- `bigboat_to_json.py`: Request the status of a BigBoat dashboard and publish 
  this data to the controller server.
- `generate_key.py`: Generate a public-private key pair and distribute the 
  public part to supporting sources (GitLab) and the controller server, for 
  registration purposes.
- `preflight.py`: Perform status checks, including integrity of secrets and the 
  controller server, before collecting and exporting data.

Finally, the repository contains a controller API and its backend daemons, and 
a deployment interface:

- `controller/auth/`: API endpoints of the controller, at which agents can 
  register themselves, pulish health status and logs, or indicate that they 
  have exported their scraped data.
- `controller/daemon.py`: Internal daemon for handling agent user creation and 
  permissions of their files.
- `daemon.py`: Internal daemon for providing update tracking and project salts 
  for use by the agent.
- `exporter_daemon.py` and `controller-export.sh`: Internal daemon for handling 
  agent's collected data to import into the database.
- `deployer.py`: Deployment web service for triggering updates.

## Docker

The data gathering scripts can be run on a centralized machine with the 
appropriate setup (see [Installation](#installation)) or within one or more 
Docker instances which collect (a part of) the data.

First, you must have a (self-signed) SSL certificate for the controller server 
which provides the API endpoints. Place the public certificate in the `certs/` 
directory. Run `docker build -t ictu/gros-data-gathering .` to build the Docker 
image. You may wish to use a registry URL in place of `ictu` and push the image 
there for distributed deployments.

Next, start the Docker instance based on the container. Use `docker run --name 
data-gathering-agent -e VAR1=value1 -e VAR2=value2 [options]... 
ictu/gros-data-gathering` to start the instance using environment variables to 
set [configuration](#configuration). By default the Docker instance 
periodically scrapes and it should be started in a daemonized form using the 
option `-d`. You can put it in a 'Jenkins-style' run using the environment 
variable `JENKINS_URL=value`. You can also enter the docker instance using 
`docker exec data-gathering-agent su agent` and run any scripts there.

With regard to the files in this repository, `docker-init.sh` is the entry 
point which sets up the periodic scraping and permissions, `docker-start.sh` 
substitutes the variables in the environment and sets up the SSH keys, while 
`docker-scraper.sh` collects data from the version control systems, exporting 
it to the controller server.

For more advanced setups with many variables that need configuration or 
persistent volume mounts, it is advisable to create 
a [docker-compose](https://docs.docker.com/compose/) file to manage the Docker 
environment.

## Configuration

A number of configuration files are used to point the scraper to the correct 
initial source locations and to apply it in a certain secured environment.

Inspect the `settings.cfg.example` and `credentials.cfg.example` files. Both 
files have sections, option names and values, and dollar signs indicate values 
that should be filled in. You can do this by copying the file to the name 
without `.example` at the end and editing it. For Docker builds, the dollar 
signs indicate environment variables (passed with `-e`) that are filled in when 
starting the instance, as explained in the [Docker](#docker) section. Many 
configuration values can also be supplied through arguments to the relevant 
pipeline scripts as shown in their `--help` output.

Some options may have their value set to a falsy value ('false', 'no', 'off', 
'-', '0' or the empty string) to disable a certain feature or to indicate that 
the setting is not used in this environment.

- jira (used by `jira_to_json.py`): JIRA access settings.
  - `server` (`$JIRA_SERVER`): Base URL of the JIRA server used by the 
    projects.
  - `username` (`$JIRA_USER`): Username to log in to JIRA with.
  - `password` (`$JIRA_PASSWORD`): Password to log in to JIRA with.
- definitions (used by `retrieve_metrics_repository.py` and 
  `project_sources.py`): Project definitions source. The settings in this 
  section may be customized per-project by suffixing the option name with 
  a period and the JIRA key of the custom project.
  - `source_type` (`$DEFINITIONS_TYPE`): Version control system used by the 
    project definitions repository, e.g., 'subversion' or 'git'.
  - `name` (`$DEFINITIONS_NAME`): The internal name of the repository.
  - `url` (`$DEFINITONS_URL`): The HTTP(S) URL from which the repository can be 
    accessed. GitLab URLs can be converted to SSH if the credentials require.
  - `path` (`$DEFINITIONS_PATH`): The local directory to check out the 
    repository to. May contain a formatter parameter `{}` which is replaced by 
    the project's quality dashboard name.
  - `base` (`$DEFINITIONS_BASE`): The name of the base library/path that is 
    required to parse the project definitions correctly.
  - `base_url` (`$DEFINITIONS_BASE_URL`): The HTTP(S) URL from which the 
    repository containing the base library for parsing project definitions can 
    be accessed. GitLab URLs can be converted to SSH.
  - `required_paths` (`$DEFINITIONS_REQUIRED_PATHS`): If non-empty, paths to 
    check out in a sparse checkout of the repository. For paths that do not 
    contain a slash, the quality metrics name is always added to the sparse 
    checkout.
- history (used by `history_to_json.py`): Quality dashboard metrics history 
  dump locations.  The settings in this section may be customized per-project 
  by suffixing the option name with a period and the JIRA key of the custom 
  project.
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
- gitlab (used by `init_gitlab.py`): Research GitLab instance where archived 
  repositories can be stored.
  - `url` (`$GITLAB_URL`): Base URL of the GitLab instance.
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
  - `artifact` (`$IMPORTER_ARTIFACT`): Path to the distribution directory 
    artifact in the job build artifacts.
- bigboat (used by `bigboat_to_json.py`): BigBoat dashboard to monitor with 
  health checks.
  - `host` (`$BIGBOAT_HOST`): Base URL of the BigBoat dashboard.
  - `key` (`$BIGBOAT_KEY`): API key to use on the BigBoat dashboard.
- jenkins (used by `jenkins_to_json.py` and `exporter/daemon.py`): Jenkins 
  instance where jobs can be started.
  - `host` (`$JENKINS_HOST`): Base URL of the Jenkins instance.
  - `username` (`$JENKINS_USERNAME`): Username to log in to the Jenkins 
    instance. Use a falsy value to not authenticate to Jenkins this way.
  - `password` (`$JENKINS_PASSWORD`): Password to log in to the Jenkins 
    instance. Use a falsy value to not authenticate to Jenkins this way.
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
- schedule (used by `daemon.py`): Schedule imposed by the controller API status
  preflight checks to let the agents check whether they should collect data.
  - `days` (`$SCHEDULE_DAYS`): Integer determining the interval in days between
     each collection run by each agent.
- ldap (used by `deployer.py`): Connection, authentication and query parameters 
  for an LDAP server.
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
- deploy (used by `deployer.py`): The deployment application.
  - `auth` (`$DEPLOYER_AUTH`): Authentication scheme to use for the deployment. 
    Accepted values are 'open' (all logins allowed, only in debug environment), 
    'pwd' (/etc/passwd), 'spwd' (/etc/shadow), and 'ldap' (LDAP server).
- projects: A list of project JIRA keys and their long names in quality metrics 
  dashboard and repositories. You may add any number of projects here; the 
  pipeline can obtain project definitions only if they have their project JIRA
  key here, are not a subproject and have a non-empty long name.
  - `$JIRA_KEY`: JIRA key of the project that the Docker instance scrapes.
  - `$PROJECT_NAME`: Name of the scraped project in the quality dashboard.
- subprojects: Subprojects and their main project.
  - `$SUBPROJECT_KEY`: JIRA key of the subproject.
- teams: GitHub teams and their main project.
  - `$TEAM_NAME`: GitHub slug of the team that manages the repositories 
    relevant to the project.
- support: JIRA key of a project and an indication of whether they are 
  considered to be a support team.
  - `$SUPPORT_TEAM`: Whether the project is considered to be a support team.

The credentials file follows a similar section-option-value, but 
`credentials.cfg.example` contains two sections: the first, whose name is 
`$SOURCE_HOST`, is to be replaced by the hostname of a version control system 
that contains the project repositories. The second section with the placeholder 
name `$DEFINITIONS_HOST`, is the hostname containing project definitions, 
matching the URLs in the `definitions` section of the settings. The two 
sections by default use separate credentials.

These sections may be edited and additional sections may be added if the 
project(s) have different setups, such as more VCS hosts. All options may be 
set to falsy values, e.g., to perform unauthenticated access to to disable 
access to the service completely.

- `env` (`$SOURCE_CREDENTIALS_ENV` and `$DEFINITIONS_CREDENTIALS_ENV`): Name of 
  the environment variable that contains the path to the SSH identity file. 
  This option is only used by Git. The references variable's value must have 
  a valid path to actually succeed in using SSH access. The path may be 
  symbolic, e.g., `~/.ssh/id_rsa`.
- `username` (`$SOURCE_USERNAME` and `$DEFINITIONS_USERNAME`): Username to log 
  in to the version control system. For GitLab with SSH, this is 'git'.
- `password` (`$SOURCE_PASSWORD` and `$DEFINITIONS_PASSWORD`): Password to log 
  in to the version control system. Ignored if `env` is not a falsy value.
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
  is a Team Foundation Server and thus has auxliary data aside from the Git 
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
  SSH URL. Useful for GitLab instaces hosted behind path-based proxies.
- `unsafe_hosts` (`$SOURCE_UNSAFE`): Disable strict HTTPS certificate and SSH 
  host key verification for the host. This works for Git SSH communication and 
  Subversion HTTPS requests.

Finally, for `topdesk_to_json.py`, the presence of a `topdesk.cfg` 
configuration file is necessary. The projects section has option names 
corresponding to JIRA keys and values corresponding to the project 
representation pass number in the CSV dump. The names section have internal 
identifiers for the columns in the CSV dump as options, and their associated 
values are the actual names in the CSV dump. The whitelist section contains 
a global whitelist, which is a regular expression that matches descriptions of 
items that are relevant events. The project-specific whitelist(s) instead match 
event descriptions that are specifically relevant to the project. The blacklist 
section can only have a global blacklist that filters irrelevant events based 
on their description.
