# Docker

The data gathering scripts can be run on a centralized machine with the 
appropriate setup (see [Installation](installation.md)) or within one or more 
Docker instances which collect (a part of) the data.

First, you must have a (self-signed) SSL certificate for the controller server 
which provides the API endpoints. Place the public certificate in the `certs/` 
directory.

Then create a `VERSION` file in the repository root containing a version string 
of the agent, which usually indicates the branch name and commit hash behind 
the module version, separated by dashes. If the `VERSION` file is not 
available, then the module version is used as is for internal purposes, but the 
version information toward other components will be degraded. Therefore, we 
recommend creating the `VERSION` file as follows from the repository:

```
echo $(grep __version__ gatherer/__init__.py | \
       sed -E "s/__version__ = .([0-9\\.]+)./\\1/")-$(git rev-parse \
       --abbrev-ref HEAD)-$(git rev-parse HEAD) > VERSION
```

Now run `docker build -t gros/data-gathering .` to build the Docker image. You 
may wish to use a registry URL before the image name and push the image there 
for distributed deployments.

Next, start a Docker instance based on the image. For example, run it with 
`docker run --name data-gathering -v env:/home/agent/env gros/data-gathering`
to start the instance using environment variables from a file called `env` to 
set [configuration](configuration.md#environment), according to the file format 
specified in that section. Ensure that the `env` file is not actually your 
virtual environment directory, which are also often called `env`. You can also 
set environment variables using the `-e VARIABLE=value` flag before the image 
name in the `docker run` command, but this is less versatile.

Depending on this configuration, the Docker instance can run in 'Daemon' mode 
or in 'Jenkins' mode. In 'Daemon' mode, the instance periodically checks if it 
should scrape data. Therefore, it should be started in a daemonized form using 
the option `-d`. Set the environment variables `CRON_PERIOD` (required) and 
`BIGBOAT_PERIOD` (optional) to appropriate periodic values (15min, hourly, 
daily) for this purpose. To start a 'Jenkins-style' run, use the environment 
variable `JENKINS_URL=value`, which performs one scrape job for the projects 
defined in the `JIRA_KEY` environment variable immediately and terminates.

As mentioned, you can pass environment variables using the Docker parameter 
`-e`, or with the `environment` section of a [Docker Compose](#compose) file. 
Additionally, configuration is read from environment files which is stored in 
`/home/agent/env` or `/home/agent/config/env`, via volume mounts as mentioned 
before. For example, you can skip some of the pre-flight checks using 
`PREFLIGHT_ARGS="--no-secrets --no-ssh"` (see all these options from 
`scraper/preflight.py`). Note that you can enter a running docker instance 
using `docker exec -it data-gathering /home/agent/scraper/agent/env.sh` which 
sets up the correct environment to run any of the scripts described in the 
[overview](overview.md).

Normal operation of an agent requires a controller setup which is able to 
handle the pre-flight checks, including registration for exchanging SSH keys 
and encryption tokens, as well as the eventual export of the collected data.

More details regarding the specific configuration of the environment within the 
Docker instance can be found in the [environment](configuration.md#environment) 
section.

## Compose

For advanced setups with many configuration variables or volume mounts, it is 
advisable to create a [docker-compose](https://docs.docker.com/compose/) file 
to manage the Docker environment and resulting scraper configuration. Any 
environment variables defined for the container are passed into the 
configuration. During the build, a file called `env` can be added to the build 
context in order to set up environment variables that remain true in all 
instances. For even more versatility, a separate configuration tool can alter 
the configuration and environment files via shared volumes.

Example setups for Docker Compose can be found in separate repositories for
[BigBoat compose](https://github.com/grip-on-software/data-gathering-compose) 
and [agent configuration](https://github.com/grip-on-software/agent-config).
