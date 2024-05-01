# Stubs for requests_ntlm.requests_ntlm (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from requests.auth import AuthBase
from typing import Any, Optional

class HttpNtlmAuth(AuthBase):
    username: Any = ...
    domain: str = ...
    password: Any = ...
    send_cbt: Any = ...
    session_security: Any = ...
    def __init__(self, username: str, password: str, session: Optional[Any] = ..., send_cbt: bool = ...) -> None: ...
    def retry_using_http_NTLM_auth(self, auth_header_field: Any, auth_header: Any, response: Any, auth_type: Any, args: Any): ...
    def response_hook(self, r: Any, **kwargs: Any): ...
    def __call__(self, r: Any): ...

class NoCertificateRetrievedWarning(Warning): ...
class UnknownSignatureAlgorithmOID(Warning): ...
