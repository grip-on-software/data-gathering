# Docker

The data gathering scripts can be run on a centralized machine with the 
appropriate setup (see [Installation](installation.md)) or within one or more 
Docker instances which collect (a part of) the data.

First, you must have a (self-signed) SSL certificate for the controller server 
which provides the API endpoints. Place the public certificate in the `certs/` 
directory. Run `docker build -t gros/data-gathering .` to build the Docker 
image. You may wish to use a registry URL before the image name and push the 
image there for distributed deployments.

Next, start the Docker instance based on the container. Use `docker run --name 
gros-data-gathering-agent -v env:/home/agent/env [options]... 
gros/data-gathering` to start the instance using environment variables from 
a file called `env` to set [configuration](configuration.md#environment). 

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
any of the scripts described in the [overview](overview.md).

For advanced setups with many configuration variables or volume mounts, it is 
advisable to create a [docker-compose](https://docs.docker.com/compose/) file 
to manage the Docker environment and resulting scraper configuration. Any 
environment variables defined for the container are passed into the 
configuration. During the build, a file called `env` can be added to the build 
context in order to set up environment variables that remain true in all 
instances. For even more versatility, a separate configuration tool can alter 
the configuration and environment files via shared volumes.

More details regarding the specific configuration of the environment within the 
Docker instance can be found in the [environment](configuration.md#environment) 
section.
