# Stubs for xlrd.book (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .biffh import *
from .formula import *
from .timemachine import *
from .sheet import Sheet
import struct
from typing import Any, Optional

unpack = struct.unpack
empty_cell: Any
USE_FANCY_CD: int
TOGGLE_GC: int
MMAP_AVAILABLE: int
USE_MMAP = MMAP_AVAILABLE
MY_EOF: int
SUPBOOK_UNK: Any
SUPBOOK_INTERNAL: Any
SUPBOOK_EXTERNAL: Any
SUPBOOK_ADDIN: Any
SUPBOOK_DDEOLE: Any
SUPPORTED_VERSIONS: Any
builtin_name_from_code: Any
code_from_builtin_name: Any

def open_workbook_xls(filename: Optional[Any] = ..., logfile: Any = ..., verbosity: int = ..., use_mmap: Any = ..., file_contents: Optional[Any] = ..., encoding_override: Optional[Any] = ..., formatting_info: bool = ..., on_demand: bool = ..., ragged_rows: bool = ...): ...

class Name(BaseObject):
    book: Any = ...
    hidden: int = ...
    func: int = ...
    vbasic: int = ...
    macro: int = ...
    complex: int = ...
    builtin: int = ...
    funcgroup: int = ...
    binary: int = ...
    name_index: int = ...
    name: Any = ...
    raw_formula: bytes = ...
    scope: int = ...
    result: Any = ...
    def cell(self): ...
    def area2d(self, clipped: bool = ...): ...

class Book(BaseObject):
    nsheets: int = ...
    datemode: int = ...
    biff_version: int = ...
    name_obj_list: Any = ...
    codepage: Any = ...
    encoding: Any = ...
    countries: Any = ...
    user_name: Any = ...
    font_list: Any = ...
    xf_list: Any = ...
    format_list: Any = ...
    format_map: Any = ...
    style_name_map: Any = ...
    colour_map: Any = ...
    palette_record: Any = ...
    load_time_stage_1: Any = ...
    load_time_stage_2: Any = ...
    def sheets(self): ...
    def sheet_by_index(self, sheetx: int) -> Sheet: ...
    def sheet_by_name(self, sheet_name: str) -> Sheet: ...
    def sheet_names(self): ...
    def sheet_loaded(self, sheet_name_or_index: Any): ...
    def unload_sheet(self, sheet_name_or_index: Any) -> None: ...
    mem: Any = ...
    filestr: Any = ...
    def release_resources(self) -> None: ...
    def __enter__(self): ...
    def __exit__(self, exc_type: Any, exc_value: Any, exc_tb: Any) -> None: ...
    name_and_scope_map: Any = ...
    name_map: Any = ...
    raw_user_name: bool = ...
    builtinfmtcount: int = ...
    addin_func_names: Any = ...
    def __init__(self) -> None: ...
    logfile: Any = ...
    verbosity: Any = ...
    use_mmap: Any = ...
    encoding_override: Any = ...
    formatting_info: Any = ...
    on_demand: Any = ...
    ragged_rows: Any = ...
    stream_len: Any = ...
    base: int = ...
    def biff2_8_load(self, filename: Optional[Any] = ..., file_contents: Optional[Any] = ..., logfile: Any = ..., verbosity: int = ..., use_mmap: Any = ..., encoding_override: Optional[Any] = ..., formatting_info: bool = ..., on_demand: bool = ..., ragged_rows: bool = ...) -> None: ...
    xfcount: int = ...
    actualfmtcount: int = ...
    def initialise_format_info(self) -> None: ...
    def get2bytes(self): ...
    def get_record_parts(self): ...
    def get_record_parts_conditional(self, reqd_record: Any): ...
    def get_sheet(self, sh_number: Any, update_pos: bool = ...): ...
    def get_sheets(self) -> None: ...
    def fake_globals_get_sheet(self) -> None: ...
    def handle_boundsheet(self, data: Any) -> None: ...
    def handle_builtinfmtcount(self, data: Any) -> None: ...
    def derive_encoding(self): ...
    def handle_codepage(self, data: Any) -> None: ...
    def handle_country(self, data: Any) -> None: ...
    def handle_datemode(self, data: Any) -> None: ...
    def handle_externname(self, data: Any) -> None: ...
    def handle_externsheet(self, data: Any) -> None: ...
    def handle_filepass(self, data: Any) -> None: ...
    def handle_name(self, data: Any) -> None: ...
    def names_epilogue(self) -> None: ...
    def handle_obj(self, data: Any) -> None: ...
    def handle_supbook(self, data: Any) -> None: ...
    def handle_sheethdr(self, data: Any) -> None: ...
    def handle_sheetsoffset(self, data: Any) -> None: ...
    def handle_sst(self, data: Any) -> None: ...
    def handle_writeaccess(self, data: Any) -> None: ...
    def parse_globals(self) -> None: ...
    def read(self, pos: Any, length: Any): ...
    def getbof(self, rqd_stream: Any): ...

def expand_cell_address(inrow: Any, incol: Any): ...
def display_cell_address(rowx: Any, colx: Any, relrow: Any, relcol: Any): ...
def unpack_SST_table(datatab: Any, nstrings: Any): ...
