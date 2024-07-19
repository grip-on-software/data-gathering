from typing import Any, Callable, Dict, List, Optional, TextIO, TypeVar, Union

__version__: str

class HTTPError(Exception):
    pass

class Request:
    headers: Dict[str, str] = ...
    method: str = ...
    show_tracebacks: bool = ...

class Response:
    status: int = ...
    headers: Dict[str, str] = ...

request = Request
response = Response

Controller = TypeVar('Controller', bound=object, covariant=True)
ExposedFunction = Callable[[Controller], str]
JSONFunction = Callable[[Controller], Union[List[Any], Dict[str, Any]]]

def expose(func: ExposedFunction, alias: Optional[str] = ...) -> ExposedFunction: ...

class Toolbox:
    @staticmethod
    def json_out() -> Callable[[JSONFunction], ExposedFunction]: ...

tools = Toolbox

def quickstart(root: Optional[Controller] = ..., script_name: str = ..., config: Optional[Union[TextIO, Dict[str, Any]]] = ...) -> None: ...
