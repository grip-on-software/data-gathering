# Stubs for xlrd.xlsx (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .timemachine import *
from .biffh import XLRDError, XL_CELL_BLANK, XL_CELL_BOOLEAN, XL_CELL_ERROR, XL_CELL_TEXT, error_text_from_code
from .book import Book, Name
from .formatting import Format, XF, is_date_format_string
from .sheet import Sheet
from typing import Any, Optional

DEBUG: int
DLF: Any
ET: Any
ET_has_iterparse: bool
Element_has_iter: bool

def ensure_elementtree_imported(verbosity: Any, logfile: Any) -> None: ...
def split_tag(tag: Any): ...
def augment_keys(adict: Any, uri: Any) -> None: ...
def cell_name_to_rowx_colx(cell_name: Any, letter_value: Any = ..., allow_no_col: bool = ...): ...

error_code_from_text: Any
U_SSML12: str
U_ODREL: str
U_PKGREL: str
U_CP: str
U_DC: str
U_DCTERMS: str
XML_SPACE_ATTR: str
XML_WHITESPACE: str
X12_MAX_ROWS: Any
X12_MAX_COLS: Any
V_TAG: Any
F_TAG: Any
IS_TAG: Any

def unescape(s: Any, subber: Any = ..., repl: Any = ...): ...
def cooked_text(self, elem: Any): ...
def get_text_from_si_or_is(self, elem: Any, r_tag: Any = ..., t_tag: Any = ...): ...
def map_attributes(amap: Any, elem: Any, obj: Any) -> None: ...
def cnv_ST_Xstring(s: Any): ...
def cnv_xsd_unsignedInt(s: Any): ...
def cnv_xsd_boolean(s: Any): ...
def make_name_access_maps(bk: Any) -> None: ...

class X12General:
    tree: Any = ...
    def process_stream(self, stream: Any, heading: Optional[Any] = ...) -> None: ...
    def finish_off(self) -> None: ...
    def dump_elem(self, elem: Any) -> None: ...
    def dumpout(self, fmt: Any, *vargs: Any) -> None: ...

class X12Book(X12General):
    bk: Any = ...
    logfile: Any = ...
    verbosity: Any = ...
    relid2path: Any = ...
    relid2reltype: Any = ...
    sheet_targets: Any = ...
    sheetIds: Any = ...
    def __init__(self, bk: Any, logfile: Any = ..., verbosity: bool = ...) -> None: ...
    core_props_menu: Any = ...
    tree: Any = ...
    def process_coreprops(self, stream: Any) -> None: ...
    @staticmethod
    def convert_filename(name: Any): ...
    def process_rels(self, stream: Any) -> None: ...
    def do_defined_name(self, elem: Any) -> None: ...
    def do_defined_names(self, elem: Any) -> None: ...
    def do_sheet(self, elem: Any) -> None: ...
    def do_workbookpr(self, elem: Any) -> None: ...
    tag2meth: Any = ...

class X12SST(X12General):
    bk: Any = ...
    logfile: Any = ...
    verbosity: Any = ...
    process_stream: Any = ...
    def __init__(self, bk: Any, logfile: Any = ..., verbosity: int = ...) -> None: ...
    def process_stream_iterparse(self, stream: Any, heading: Optional[Any] = ...) -> None: ...
    tree: Any = ...
    def process_stream_findall(self, stream: Any, heading: Optional[Any] = ...) -> None: ...

class X12Styles(X12General):
    bk: Any = ...
    logfile: Any = ...
    verbosity: Any = ...
    xf_counts: Any = ...
    xf_type: Any = ...
    fmt_is_date: Any = ...
    def __init__(self, bk: Any, logfile: Any = ..., verbosity: int = ...) -> None: ...
    def do_cellstylexfs(self, elem: Any) -> None: ...
    def do_cellxfs(self, elem: Any) -> None: ...
    def do_numfmt(self, elem: Any) -> None: ...
    def do_xf(self, elem: Any) -> None: ...
    tag2meth: Any = ...

class X12Sheet(X12General):
    sheet: Any = ...
    logfile: Any = ...
    verbosity: Any = ...
    rowx: int = ...
    bk: Any = ...
    sst: Any = ...
    relid2path: Any = ...
    relid2reltype: Any = ...
    merged_cells: Any = ...
    warned_no_cell_name: int = ...
    warned_no_row_num: int = ...
    process_stream: Any = ...
    def __init__(self, sheet: Any, logfile: Any = ..., verbosity: int = ...) -> None: ...
    def own_process_stream(self, stream: Any, heading: Optional[Any] = ...) -> None: ...
    def process_rels(self, stream: Any) -> None: ...
    def process_comments_stream(self, stream: Any) -> None: ...
    def do_dimension(self, elem: Any) -> None: ...
    def do_merge_cell(self, elem: Any) -> None: ...
    def do_row(self, row_elem: Any) -> None: ...
    tag2meth: Any = ...

def open_workbook_2007_xml(zf: Any, component_names: Any, logfile: Any = ..., verbosity: int = ..., use_mmap: int = ..., formatting_info: int = ..., on_demand: int = ..., ragged_rows: int = ...): ...
