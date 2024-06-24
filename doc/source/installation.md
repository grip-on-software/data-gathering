# Installation

The data gathering scripts and modules require Python version 3.8 and higher. 
Version 0.0.3 is the last version to support Python 3.6, 3.7 and the old 
quality reporting source.

The scripts have been tested on MacOS 10.14+, Ubuntu 16.04+, CentOS 7.3+ as 
well as on some Windows versions.

The scripts and modules are two separate concepts with regard to installation: 
the data gathering module `gatherer` must be installed so that the scripts can 
always locate the module. Additionally, the scripts and modules have 
dependencies which must be installed. Each of these steps can be done 
separately or in combination with one another:

- Run `make setup` to install the dependencies for the data gathering modules.
  - For the agent, `make setup_agent` installs the dependency for the scraper 
    web API as well as dependencies for the modules.
  - If you want to gather data from spreadsheets with seat counts, Topdesk or 
    LDAP: run `make setup_jenkins`, which also ensures that the dependencies 
    for the modules are installed.
  - For the controller: run `make setup_daemon`, which also ensures that the 
    dependencies for the modules are installed.
  - For tests: run `make setup_test`, which also installs the dependencies for 
    the modules.
  - For static code analysis: run `make setup_analysis`, which installs 
    dependencies for Pylint and mypy (typing extensions) as well as all the 
    other dependencies, even those in scraper agent, Jenkins and controller 
    setups.
- Run `make install` to install the module from source, including dependencies 
  for the module if they were not yet installed. Note that some versions of 
  `setuptools`, which is used in this step, are unable to use wheels or eggs 
  even if they are supported by the platform. Due to the additional compilation 
  time required for some source packages, running both a command from the 
  options above and this command is likely faster than only `make setup`.
- Instead of running the scripts from this repository to install, you can use 
  `pip install gros-gatherer` to obtain the latest release version of the 
  module and its dependencies from PyPI.

We recommend creating a virtual environment to manage the dependencies. Make 
sure that `python` runs the Python version in the virtual environment. 
Otherwise, the dependencies are installed to the system libraries path or the 
user's Python libraries path if you do not have access to the system libraries. 

## Controller

For the controller setup, a virtual environment must be created beneath 
`/usr/local/envs` (create this directory) named `controller` with the 
dependencies above. Next, continue with the following steps:

- Configure the agent, controller or development environment using the settings 
  and credentials files as explained in the [configuration](configuration.md) 
  section.
- For the controller: use `sudo ./controller/setup.sh` to create services and 
  symlink scripts to make them available for the services.

Some agent scripts and controller services interact with a database for update 
trackers, project salts and status information storage. This database must be 
a MonetDB instance pre-installed in the environment where the controller is 
able to access it directly.
