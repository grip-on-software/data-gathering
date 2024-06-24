# Modes

The data gathering scripts and modules are able to be deployed in different 
software development ecosystem setups. There are several ways to use the 
scripts and modules, depending on the situation that they are used in:

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
- Module: Certain components of this Python package are usable standalone as 
  a wrapper to interact with various APIs and check status of certain services, 
  such as Jira, Jenkins or Git, in other applications. Examples of such 
  applications are a [data gathering agent status 
  dashboard](https://github.com/grip-on-software/status-dashboard) and 
  a [deployment quality gate](https://github.com/grip-on-software/deployer).
