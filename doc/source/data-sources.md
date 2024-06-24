# Data sources

The following list provides the supported version of platforms that the data 
gatherer can use. The versions listed here are indication of which actual 
version of the sources have been used in deployments and tests with the modules 
and do not indicate if this is the only supported version. Later versions are 
likely supported unless noted otherwise.

- Jira: Tested with Jira 7.9.2 and later with Agile 7.3.1 and later.
- Version control systems:
  - Git: Tested with Git clients with version 1.8.3 and later. Supported review 
    systems are GitHub, GitLab and Azure DevOps (TFS/VSTS).
    - GitLab: Tested with version 9.4 and later.
    - Azure DevOps: Tested with TFS versions 2015, 2017 and 2018.
  - Subversion: Tested with server version 1.6 and later and client version 1.7 
    and later.
- Jenkins: Works with LTS versions.
- Quality-time: Works with version 5.9.0 and later. Note that internal API is 
  used, so support may break, tested with version 5.12.0.
- SonarQube: Works with version 8.0 and later. Organization support for 
  SonarCloud included; for later versions, you may need to set the URL to 
  a specific component to avoid collecting from the entire instance. Note that 
  some internal APIs may be used, so support may break.
- BigBoat: Works with BigBoat version 5.0 and later.
- Additional data is retrievable with scripts from seat count spreadsheets, 
  Topdesk and LDAP servers with proper configuration.
