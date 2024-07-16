# API endpoints

In some software development ecosystems, it is necessary to separate the data 
acquisition process from the import control. This is usually achieved with an 
agent and controller setup to perform these two tasks in isolated networks. In 
order to have agents properly collect data at scheduled intervals and provide 
this to the controller server for further processing and import, we need to 
exchange data regarding status and registration. This is where two APIs come 
into play. This document provides an overview of the APIs, also as a starting 
point to set up this agent-based networking in a virtualized ecosystem.

This is an advanced setup which requires a central system with proper user 
access management such that controller services can automatically manage 
permissions through `sudo` calls. Additionally, the agents are set up through 
Docker Compose with the data gathering scripts and modules as well as 
a configuration interface. Updates to the instances could be deployed using 
automation for Docker platforms, such as with BigBoat (which is no longer 
maintained).

## Scraper agent web API

In the [Docker instance](docker.md) of the agent when running the 'Daemon' 
mode, one can make use of a web API to collect status information about the 
agent and immediately start a scrape operation. By default, the web API server 
runs on port 7070. The API uses JSON as an output format. The following 
endpoints are provided:

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

More details on the scraper API are found in the 
[schemas](https://gros.liacs.nl/schema/data-gathering.html#data-gathering-controller) 
or in the [Swagger 
UI](https://gros.liacs.nl/swagger/?urls.primaryName=Data%20gathering%20scraper%20agent%20API%20%28view%20only%29).

## Controller API

The controller is meant to run on a host that is accessible by the scraper 
agents in order to exchange information with the agents, databases and 
Jenkins-style scrape jobs. Setup of this host requires some extensive 
configuration of directories and users/permissions in order to keep data secure 
during the scrape process while allowing administration of the agent users. The 
`controller` directory provides a few services which play a role in setting up 
all the backend services. The services require a specific 
[installation](installation.md#controller) in order to function, along with 
additional directories `/agents` and `/controller` and system users.

There are three backend daemon services which focus on different tasks during 
the agent-based data acquisition process:

- The controller daemon handles agent user creation, setting up proper 
  permissions for home directories to exchange data from the agent to the other 
  services through SSH key identities and cleaning up afterwards. It runs as 
  the `controller` system user in the `controller` group and requires `sudo` 
  rights to execute the following binaries: `useradd`, `adduser`, `mkdir`, 
  `rm`, `chown` and `chmod`.
- The exporter daemon handles export of the agent data from the exchanged home 
  directories and import into the database using the Java importer as well as 
  remote Jenkins scrape job build execution. It runs as the `exporter` system 
  user in the `controller` group and requires `sudo` rights to execute the 
  following binaries: `mkdir`, `rm`, `chown` and `chmod`.
- The gatherer daemon checks database status of agent data, update trackers, 
  manages schedules for frequent data acquisition runs, provides encryption 
  functionalities and receives health status information from BigBoat. It runs 
  as the `gatherer` system user in the `controller` group and does not require 
  any elevated rights.

A web API is exposed by the controller API, provided from the `controller/auth` 
directory. The API is meant to run on HTTPS port 443, with a certificate 
provided in the `certs` directory, which may be self-signed (and in that case 
the agents must have the public part as well). The following endpoints exist:

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

More details on the controller API are found in the 
[schemas](https://gros.liacs.nl/schema/data-gathering.html#data-gathering-controller) 
or in the [Swagger 
UI](https://gros.liacs.nl/swagger/?urls.primaryName=Data%20gathering%20controller%20API%20%28view%20only%29).

Note that next to the controller API, the agents also connect to the controller 
via SSH port 22 after registration in order to upload batches of collected data 
before signalling the new upload on the `export.py` endpoint.
