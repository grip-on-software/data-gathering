Software development process data gathering
===========================================

Data gathering is a collection of Python modules and scripts that acquire data 
from different data systems in use by software development organizations, teams 
and projects. The data is used in the [Grip on Software](https://gros.liacs.nl) 
(GROS) research project, involving a larger pipeline where the gathered data is 
made available for analysis and reporting through a database setup, and as such 
the modules and scripts are aimed at exporting data in JSON formats, according 
to a defined schema.

Each data gathering script reads data from a source based on the requested 
project and any additional parameters (command-line arguments, settings and 
credentials). The exported JSON file usually contains a pre-formatted list of 
objects with properties. The schemas are described in the [Grip on Software 
data schemas](https://gros.liacs.nl/schema/) documentation. The exported data 
is suited for import into a MonetDB database.

This documentation describes the steps to set up the data gathering modules and 
scripts. It augments the README.md file part of the Git repository that is also 
published on the [PyPI repository](https://pypi.org/project/gros-gatherer/), 
which introduces the modules from an installation and development standpoint.

```{toctree}
:maxdepth: 1
:caption: Introduction

modes.md
overview.md
data-sources.md
```

```{toctree}
:maxdepth: 2
:caption: Contents

installation.md
docker.md
api.md
configuration.md
changelog.md
```
