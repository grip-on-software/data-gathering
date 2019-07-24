# Stubs for git.config (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

import abc
from typing import Any, Optional, Union

class MetaParserBuilder(abc.ABCMeta):
    def __new__(cls, name: Any, bases: Any, clsdict: Any): ...

class SectionConstraint:
    def __init__(self, config: Any, section: Any) -> None: ...
    def __del__(self) -> None: ...
    def __getattr__(self, attr: Any): ...
    @property
    def config(self): ...
    def release(self): ...
    def __enter__(self): ...
    def __exit__(self, exception_type: Any, exception_value: Any, traceback: Any) -> None: ...

class GitConfigParser:
    t_lock: Any = ...
    re_comment: Any = ...
    optvalueonly_source: str = ...
    OPTVALUEONLY: Any = ...
    OPTCRE: Any = ...
    def __init__(self, file_or_files: Any, read_only: bool = ..., merge_includes: bool = ...) -> None: ...
    def __del__(self) -> None: ...
    def __enter__(self): ...
    def __exit__(self, exception_type: Any, exception_value: Any, traceback: Any) -> None: ...
    def release(self) -> None: ...
    def optionxform(self, optionstr: Any): ...
    def read(self) -> None: ...
    def items(self, section_name: Any): ...
    def write(self) -> None: ...
    def add_section(self, section: Any): ...
    @property
    def read_only(self): ...
    def get_value(self, section: str, option: str, default: Optional[Union[int, float, str, bool]] = ...) -> Union[int, float, str, bool]: ...
    def set_value(self, section: str, option: str, value: Union[int, float, str, bool]) -> 'GitConfigParser': ...
    def rename_section(self, section: Any, new_name: Any): ...