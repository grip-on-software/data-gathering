# Stubs for gitlab.config (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Optional

class ConfigError(Exception): ...
class GitlabIDError(ConfigError): ...
class GitlabDataError(ConfigError): ...
class GitlabConfigMissingError(ConfigError): ...

class GitlabConfigParser:
    gitlab_id: Any = ...
    url: Any = ...
    ssl_verify: bool = ...
    timeout: int = ...
    private_token: Any = ...
    oauth_token: Any = ...
    http_username: Any = ...
    http_password: Any = ...
    api_version: str = ...
    per_page: Any = ...
    def __init__(self, gitlab_id: Optional[Any] = ..., config_files: Optional[Any] = ...) -> None: ...
