# Configuration

A number of configuration files are used to point the scraper to the correct 
initial source locations and to apply it in a certain secured environment.

Inspect the `settings.cfg.example` and `credentials.cfg.example` files. Both 
files have sections, option names and values, and dollar signs indicate values 
that should be filled in. You can do this by copying the file to the name 
without `.example` at the end and editing it. For Docker builds, the dollar 
signs indicate environment variables that are filled in when starting the 
instance, as explained in the [Docker](docker.md) section. Many configuration 
values can also be supplied through arguments to the relevant pipeline scripts 
as shown in their `--help` output.

Some options may have their value set to a falsy value ('false', 'no', 'off', 
'-', '0' or the empty string) to disable a certain feature or to indicate that 
the setting is not used in this environment.

## Settings

- jira (used by `jira_to_json.py`): Jira access settings.
  - `server` (`$JIRA_SERVER`): Base URL of the Jira server used by the 
    projects.
  - `username` (`$JIRA_USER`): Username to log in to Jira with. This may also
    be provided in a credentials section for the instance's network location 
    (domain and optional port).
  - `password` (`$JIRA_PASSWORD`): Password to log in to Jira with. This may 
    also be provided in a credentials section for the instance's network 
    location (domain and optional port).
- quality-time (used by `project_sources.py`): Quality Time source for
  project definitions and metrics history.
  - `name` (`$QUALITY_TIME_NAME`): The source name of the Quality Time server, 
    to give it a unique name within the sources of the project.
  - `url` (`$QUALITY_TIME_URL`): The HTTP(S) URL from which the Quality Time 
    main landing UI page can be found.
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
- sonar (used by `project_sources.py`): SonarQube instance where we can 
  retrieve metrics and potentially project definitions.
  - `name` (`$SONAR_NAME`): The source name of the SonarQube server, to give it 
    a unique name within the sources of the project.
  - `url` (`$SONAR_URL`): The HTTP(S) URL from which the SonarQube main landing 
    UI page can be found.
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

## Credentials

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
unauthenticated access or to disable access to the service completely.

- `env` (`$SOURCE_CREDENTIALS_ENV` and `$DEFINITIONS_CREDENTIALS_ENV`): Name of 
  the environment variable that contains the path to the SSH identity file. 
  This option is only used by sources that are accessible with SSH, namely Git 
  and review systems based on it (GitHub, GitLab, TFS). The referenced 
  environment variable's value must be set to a valid path to actually succeed 
  in using SSH access. The path may be symbolic, e.g., `~/.ssh/id_rsa`. 
  Connections to retrieve the Git repository always use SSH if this option is 
  set, even if the source is initially given with an HTTP/HTTPS URL.
- `username` (`$SOURCE_USERNAME` and `$DEFINITIONS_USERNAME`): Username to log 
  in to the version control system. This may differ by protocol used, and as 
  such one may additionally define `username.ssh` and `username.http` which 
  override the default key. For example, with GitLab/GitHub with SSH, this is 
  'git' but it is the username when accessing via HTTP(S).
- `password` (`$SOURCE_PASSWORD` and `$DEFINITIONS_PASSWORD`): Password to log 
  in to the version control system. Ignored if we connect to the version 
  control system using SSH, e.g., when `env` is not a falsy value.
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
- `gitlab_token` (`$SOURCE_GITLAB_TOKEN`): API token for GitLab instances in 
  order to obtain auxiliary data from GitLab or interface with its 
  authorization scheme.
- `tfs` (`$SOURCE_TFS`): Set to a non-falsy value to indicate that the source 
  is a Team Foundation Server and thus has auxiliary data aside from the Git 
  repository. If this is true, then any collections are discovered based on the 
  initial source that we have are collected, otherwise the value must be 
  a collection name starting with `tfs/`. Any projects within or beneath the 
  collection may then be gathered.
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
- `unsafe_hosts` (`$SOURCE_UNSAFE` and `$DEFINITIONS_UNSAFE`): Disable strict 
  HTTPS certificate and SSH host key verification for the host. This works for 
  Git SSH communication, Subversion HTTPS requests and some sources with APIs.
- `skip_stats` (`$SOURCE_SKIP_STATS`): Disable collection of statistics on 
  commit sizes from repositories at this source.
- `agile_rest_path` (used by `jira` source type): The REST path to use for Jira 
  Agile requests. Set to `agile` in order to use the public API.
- `host`: The hostname and optional port to use instead of the host in the 
  configuration section. If this is set to a non-falsy value, then most other 
  options in the section are ignored and the options from the referenced 
  section are used, which must exist. The referenced hostname and port are used 
  in URLs to connect to the source. Depending on the source, the original 
  protocol scheme and further path components are used as is, barring other 
  options like `strip`. Recursive redirections of this kind are not supported.

## Environment

When running the scraper agent using [Docker](docker.md), as mentioned in that 
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
  that additional arguments and functionality should be provided to upload log 
  messages at WARNING level or above to a logger server on the controller host. 
  Aside from this functionality, the 'Daemon' mode of the agent always uploads 
  the entire log to the controller at the end of a scrape for a project.
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

## Issue trackers (Jira and Azure DevOps)

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

## Seats

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

## Topdesk

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
