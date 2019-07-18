# Stubs for xlrd.sheet (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .biffh import *
from .timemachine import *
from .formatting import Format, nearest_colour_index
from .formula import FMLA_TYPE_CELL, FMLA_TYPE_SHARED, decompile_formula, dump_formula
from typing import Any, Optional

OBJ_MSO_DEBUG: int

class Sheet(BaseObject):
    name: str = ...
    book: Any = ...
    nrows: int = ...
    ncols: int = ...
    colinfo_map: Any = ...
    rowinfo_map: Any = ...
    col_label_ranges: Any = ...
    row_label_ranges: Any = ...
    merged_cells: Any = ...
    rich_text_runlist_map: Any = ...
    defcolwidth: Any = ...
    standardwidth: Any = ...
    default_row_height: Any = ...
    default_row_height_mismatch: Any = ...
    default_row_hidden: Any = ...
    default_additional_space_above: Any = ...
    default_additional_space_below: Any = ...
    visibility: int = ...
    gcw: Any = ...
    hyperlink_list: Any = ...
    hyperlink_map: Any = ...
    cell_note_map: Any = ...
    vert_split_pos: int = ...
    horz_split_pos: int = ...
    horz_split_first_visible: int = ...
    vert_split_first_visible: int = ...
    split_active_pane: int = ...
    has_pane_record: int = ...
    horizontal_page_breaks: Any = ...
    vertical_page_breaks: Any = ...
    biff_version: Any = ...
    logfile: Any = ...
    bt: Any = ...
    bf: Any = ...
    number: Any = ...
    verbosity: Any = ...
    formatting_info: Any = ...
    ragged_rows: Any = ...
    put_cell: Any = ...
    first_visible_rowx: int = ...
    first_visible_colx: int = ...
    gridline_colour_index: int = ...
    gridline_colour_rgb: Any = ...
    cooked_page_break_preview_mag_factor: int = ...
    cooked_normal_view_mag_factor: int = ...
    cached_page_break_preview_mag_factor: int = ...
    cached_normal_view_mag_factor: int = ...
    scl_mag_factor: Any = ...
    utter_max_rows: int = ...
    utter_max_cols: int = ...
    def __init__(self, book: Any, position: Any, name: Any, number: Any) -> None: ...
    def cell(self, rowx: Any, colx: Any): ...
    def cell_value(self, rowx: int, colx: int) -> str: ...
    def cell_type(self, rowx: Any, colx: Any): ...
    def cell_xf_index(self, rowx: Any, colx: Any): ...
    def row_len(self, rowx: Any): ...
    def row(self, rowx: Any): ...
    def get_rows(self): ...
    def row_types(self, rowx: Any, start_colx: int = ..., end_colx: Optional[Any] = ...): ...
    def row_values(self, rowx: Any, start_colx: int = ..., end_colx: Optional[Any] = ...): ...
    def row_slice(self, rowx: Any, start_colx: int = ..., end_colx: Optional[Any] = ...): ...
    def col_slice(self, colx: Any, start_rowx: int = ..., end_rowx: Optional[Any] = ...): ...
    def col_values(self, colx: Any, start_rowx: int = ..., end_rowx: Optional[Any] = ...): ...
    def col_types(self, colx: Any, start_rowx: int = ..., end_rowx: Optional[Any] = ...): ...
    col: Any = ...
    def tidy_dimensions(self) -> None: ...
    def put_cell_ragged(self, rowx: Any, colx: Any, ctype: Any, value: Any, xf_index: Any) -> None: ...
    def put_cell_unragged(self, rowx: Any, colx: Any, ctype: Any, value: Any, xf_index: Any) -> None: ...
    def read(self, bk: Any): ...
    def string_record_contents(self, data: Any): ...
    def update_cooked_mag_factors(self) -> None: ...
    def fixed_BIFF2_xfindex(self, cell_attr: Any, rowx: Any, colx: Any, true_xfx: Optional[Any] = ...): ...
    def insert_new_BIFF20_xf(self, cell_attr: Any, style: int = ...): ...
    def fake_XF_from_BIFF20_cell_attr(self, cell_attr: Any, style: int = ...): ...
    def req_fmt_info(self) -> None: ...
    def computed_column_width(self, colx: Any): ...
    def handle_hlink(self, data: Any): ...
    def handle_quicktip(self, data: Any) -> None: ...
    def handle_msodrawingetc(self, recid: Any, data_len: Any, data: Any) -> None: ...
    def handle_obj(self, data: Any): ...
    def handle_note(self, data: Any, txos: Any) -> None: ...
    def handle_txo(self, data: Any): ...
    def handle_feat11(self, data: Any) -> None: ...

class MSODrawing(BaseObject): ...
class MSObj(BaseObject): ...
class MSTxo(BaseObject): ...

class Note(BaseObject):
    author: Any = ...
    col_hidden: int = ...
    colx: int = ...
    rich_text_runlist: Any = ...
    row_hidden: int = ...
    rowx: int = ...
    show: int = ...
    text: Any = ...

class Hyperlink(BaseObject):
    frowx: Any = ...
    lrowx: Any = ...
    fcolx: Any = ...
    lcolx: Any = ...
    type: Any = ...
    url_or_path: Any = ...
    desc: Any = ...
    target: Any = ...
    textmark: Any = ...
    quicktip: Any = ...

def unpack_RK(rk_str: Any): ...

cellty_from_fmtty: Any
ctype_text: Any

class Cell(BaseObject):
    ctype: Any = ...
    value: Any = ...
    xf_index: Any = ...
    def __init__(self, ctype: Any, value: Any, xf_index: Optional[Any] = ...) -> None: ...

empty_cell: Any

class Colinfo(BaseObject):
    width: int = ...
    xf_index: int = ...
    hidden: int = ...
    bit1_flag: int = ...
    outline_level: int = ...
    collapsed: int = ...

class Rowinfo(BaseObject):
    height: Any = ...
    has_default_height: Any = ...
    outline_level: Any = ...
    outline_group_starts_ends: Any = ...
    hidden: Any = ...
    height_mismatch: Any = ...
    has_default_xf_index: Any = ...
    xf_index: Any = ...
    additional_space_above: Any = ...
    additional_space_below: Any = ...
    def __init__(self) -> None: ...
