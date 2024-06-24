Software development process data gathering
===========================================

[![PyPI](https://img.shields.io/pypi/v/gros-gatherer.svg)](https://pypi.python.org/pypi/gros-gatherer)
[![Build 
status](https://github.com/grip-on-software/data-gathering/actions/workflows/gatherer-tests.yml/badge.svg)](https://github.com/grip-on-software/data-gathering/actions/workflows/gatherer-tests.yml)
[![Coverage 
Status](https://coveralls.io/repos/github/grip-on-software/data-gathering/badge.svg?branch=master)](https://coveralls.io/github/grip-on-software/data-gathering?branch=master)
[![Quality Gate
Status](https://sonarcloud.io/api/project_badges/measure?project=grip-on-software_data-gathering&metric=alert_status)](https://sonarcloud.io/project/overview?id=grip-on-software_data-gathering)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.10911862.svg)](https://doi.org/10.5281/zenodo.10911862)

The Python modules in this repository gather data from different sources that 
are used by software development teams and projects, as well as control 
a distributed setup of data gathering. The data gathering modules are part of 
Grip on Software, a research project involving a larger pipeline where the 
gathered data is made available for analysis purposes through a MonetDB 
database setup.

The following systems from software development processes are able to be 
interacted with using the GROS gatherer modules, focusing on data acquisition:

- Jira
- Git, including additional repository data from GitHub and GitLab
- Azure DevOps/VSTS/TFS, including Git-based data
- Subversion
- Jenkins
- Quality-time
- SonarQube
- BigBoat

There are many ways to use the GROS gatherer, such as manual script usage, 
Docker images, Jenkins jobs, agent-based Docker compose network isolation, 
central controller instances and usage in other applications. However, this 
README.md document focuses on the module installation and development. More 
thorough documentation on compatibility with versions of data sources, 
configuration, script overviews and agent-controller APIs is found in the 
[online data-gathering documentation](https://gros.liacs.nl/data-gathering/).

## Installation

The data gathering modules require Python version 3.8 and higher.

To obtain the latest release version of the module and its dependencies from 
PyPI, use the following command:

```
pip install gros-gatherer
```

We recommend creating a virtual environment to manage your dependencies. Make 
sure that `python` runs the Python version in the virtual environment. 
Otherwise, the dependencies are installed to the system libraries path or the 
user's Python libraries path if you do not have access to the system libraries. 

## Configuration

Some modules require the existence of settings and credentials files in the 
directory from which the script importing the module is run. This path is 
adjustable with environment variables. For details on configuration, view the 
[documentation](https://gros.liacs.nl/data-gathering/configuration.html).

## Development and testing

Most of the modules come with unit tests, while also depending on the 
correctness of dependencies to provide accurate data from sources (i.e. our 
unit tests often use mocks in place of the dependencies) and testing the actual 
system in non-production settings. To run unit tests in this repository, first 
install the test dependencies with `make setup_test` which also installs all 
dependencies for the modules. Then `coverage run tests.py` provides test 
results in the output, with XML versions compatible with, e.g., JUnit and 
SonarQube available in the `test-reports/` directory. Detailed information on 
test coverage is also obtainable after a test run in various report formats, 
for example:

- `coverage report -m` for a report on (counts of) statements and branches that 
  were hit and missed in the modules in the output.
- `coverage html` for a HTML report in the `htmlcov/` directory.
- `coverage xml -i` for an XML output suitable for, e.g., SonarQube.

To perform all the steps except the HTML report, run `make coverage`. If you do 
not need XML outputs (each test class writes an XML file by default), then run 
`make test` to just report on test successes and failures or `make cover` to 
also have the terminal report on statement/branch hits/misses.

[GitHub Actions](https://github.com/grip-on-software/data-gathering/actions) is 
used to run the unit tests and report on coverage on commits and pull requests. 
This includes quality gate scans tracked by 
[SonarCloud](https://sonarcloud.io/project/overview?id=grip-on-software_data-gathering) 
and [Coveralls](https://coveralls.io/github/grip-on-software/data-gathering) 
for coverage history.

The Python scripts and modules conform to code style and typing standards which 
may be checked using Pylint with `make pylint` and mypy with `make mypy`, 
respectively, after running `make setup_analysis` to install static code 
analysis tools. The command for mypy provides potential errors in the output 
and typing coverage reports in several formats, including XML (compatible with 
JUnit and  SonarQube) in the `mypy-report/` directory. To also receive the HTML 
report, use `make mypy_html` instead.

Finally, the schemas in the `schema/` directory allow validation of certain 
configuration files as well as all the exported artifacts against the schema. 
For example, the Jira and Azure DevOps field mapping specifications are able to 
be checked; see the [issue 
trackers](https://gros.liacs.nl/data-gathering/configuration.html#issue-trackers-jira-and-azure-devops) 
documentation section for an example.

We publish releases to [PyPI](https://pypi.org/project/gros-gatherer/) using 
`make setup_release` to install dependencies from `requirements-release.txt` 
and `make release` which performs multiple checks: unit tests, typing, lint and 
version number consistency. The release files are also published on 
[GitHub](https://github.com/grip-on-software/data-gathering/releases) and from 
there are archived on [Zenodo](https://zenodo.org/doi/10.5281/zenodo.10911861). 
Noteworthy changes to the modules are added to the 
[changelog](https://gros.liacs.nl/data-gathering/changelog.html).

## License

Data gathering scripts and modules are licensed under the Apache 2.0 License.
