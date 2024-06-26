# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) 
and we adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Unit tests for the `bigboat`, `config`, `database`, `domain`, `files`, 
  `jenkins`, `jira`, `log`, `project_definition`, `request`, `salt`, `table`, 
  `update`, `utils`, `version_control` and `vsts` modules added.
- Method `Configuration.clear` added to clear class instances.
- Support for Quality-time 5.9.0 and later added, tested with version 5.12.0.
- Support for SonarQube 8.0 and later added.
- Support for Python 3.9 through 3.12 added.
- Jenkins job `default_parameters` now checks the `"property"` key from the API 
  for support of newer Jenkins versions.
- Sources set supports set construction signature and direct set operations.
- Table classes support retrieving the `filename` property and operations for 
  clearing, contains check, iterating and checking the length of the table.
- Key table and link table handle contains checks in a more tolerant way, 
  allowing missing keys, combinations of encrypted, unencrypted and 
  intermediate data (with conversions of usernames applied) and support 
  updating rows with the key provided in the update row as long as it is the 
  same. Both now also support subscription with a key or tuple of keys between 
  the square brackets.
- Jira methods that create structures like issue fields, table objects and 
  changelog fields return the field, and added property accessors for the 
  fields and changelog object. Can also retrieve projects from the project 
  parser if they are prefetched, and the query and iterator limiter.

### Changed

- Dependencies updated. All requirements are tagged to specific versions.
- Git sources normalize SSH URLs that can be formatted as SCP-style by 
  stripping initial slashes from path names.
- Domain sources use the changed host name for credentials sections instead of 
  the original host name in some cases, so that original SSH URLs do not need
  an `env` option in the original host name section and HTTP URLs do not need
  `username` and `password` options. Only situations that specifically need the 
  original host name do so, like the GitLab source's `group` option.
- File store exceptions are now always `RuntimeError` or subclasses.
- Jenkins requests for the crumb token are postponed until the request session 
  is used instead of when the instance is created, are tried again if there is 
  an exception and are not requested again if the HTTP status code is 404.
- Jenkins API exceptions, including connection errors, timeouts and HTTP status 
  codes are handled and replaced with `RequestException` with exception source.
- Salt utility class raises a `RuntimeError` when the database connection is 
  necessary but unavailable instead of propagating database exceptions.
- Jira class hierarchy changed so that different types of base field classes 
  can be used for fetch/parse methods of issue fields and fetch/parse methods 
  of changelog fields, same for special fields.
- Package is now a `pyproject.toml` project instead of using `setup.py`.
- Docker build no longer reads `env` files (should be added as volume instead, 
  or use Compose environment sections in case an initial `env` file cannot be 
  provided during startup), does include the `vsts_fields.json` file and the 
  `VERSION` file is now optional (version information is degraded if missing).

### Removed

- Support for Python 3.6 and Python 3.7 dropped.
- Support for the Quality report source dropped.

### Fixed

- Git sources provide the correct path name if the eventual URL can be 
  formatted as SCP-style.
- Consider a URL with only a domain name, a colon and a path to already be an 
  SCP URL when converting Git-SSH URLs, i.e., do not require a username to be 
  present.
- TFS API credentials now use the `username.http` option or the username
  from the URL, if those are available and the `username` option.
- TFVC project was always an empty string.
- Domain source URLs are adjusted even if no credentials section is provided.
- Jenkins objects that are invalidated also have their `exists` value reset.
- Jenkins view objects now have correct URLs.
- Jenkins job objects now include parent job in equality checks if it exists so 
  that a job named `'test-job/branch-job'` is not the same as `'branch-job'`.
- Jenkins build objects that do not exist now have number 0 instead of raising 
  an exception when requesting the `number` property.
- Jenkins build objects now properly implement `<=` and >=` operators.
- Update: Database tracker no longer performs an update query which matches no 
  rows when the project ID is not found.
- Iterator limiter avoids setting the page size to a value of zero or less.
- Jira sprint field data now properly handles missing start and end dates, and
  avoid losing sprint details if there are multiple equals signs in the 
  key-value entries.
- Jira first changelog version would sometimes receive the updated date of the 
  second version.
- Jira developer parser no longer tries to parse a user whose name is null
- Jira default latest update string led to invalid timestamp comparisons.
- Jira comment field had potential unset variable.
- TFS/VSTS/ADO empty tags field is now seen as having zero tags instead of one.

## [0.0.3] - 2024-04-03

### Added

- Initial release of version as used during the GROS research project. 
  Previously, versions were rolling releases based on Git commits.

### Removed

- Support for Python 2.7 dropped.
- Support for GitLab legacy v3 API (for GitLab version 8) dropped.

[Unreleased]: 
https://github.com/grip-on-software/data-gathering/compare/v0.0.3...HEAD
[0.0.3]: https://github.com/grip-on-software/data-gathering/releases/tag/v0.0.3
