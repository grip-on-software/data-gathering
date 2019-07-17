# Stubs for gitdb.pack (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from gitdb.util import LazyMixin
from typing import Any, Optional

class IndexWriter:
    def __init__(self) -> None: ...
    def append(self, binsha: Any, crc: Any, offset: Any) -> None: ...
    def write(self, pack_sha: Any, write: Any): ...

class PackIndexFile(LazyMixin):
    index_v2_signature: bytes = ...
    index_version_default: int = ...
    def __init__(self, indexpath: Any) -> None: ...
    def close(self) -> None: ...
    def version(self): ...
    def size(self): ...
    def path(self): ...
    def packfile_checksum(self): ...
    def indexfile_checksum(self): ...
    def offsets(self): ...
    def sha_to_index(self, sha: Any): ...
    def partial_sha_to_index(self, partial_bin_sha: Any, canonical_length: Any): ...
    def sha_to_index(self, sha: Any): ...

class PackFile(LazyMixin):
    pack_signature: int = ...
    pack_version_default: int = ...
    first_object_offset: Any = ...
    footer_size: int = ...
    def __init__(self, packpath: Any) -> None: ...
    def close(self) -> None: ...
    def size(self): ...
    def version(self): ...
    def data(self): ...
    def checksum(self): ...
    def path(self): ...
    def collect_streams(self, offset: Any): ...
    def info(self, offset: Any): ...
    def stream(self, offset: Any): ...
    def stream_iter(self, start_offset: int = ...): ...

class PackEntity(LazyMixin):
    IndexFileCls: Any = ...
    PackFileCls: Any = ...
    def __init__(self, pack_or_index_path: Any) -> None: ...
    def close(self) -> None: ...
    def info(self, sha: Any): ...
    def stream(self, sha: Any): ...
    def info_at_index(self, index: Any): ...
    def stream_at_index(self, index: Any): ...
    def pack(self): ...
    def index(self): ...
    def is_valid_stream(self, sha: Any, use_crc: bool = ...): ...
    def info_iter(self): ...
    def stream_iter(self): ...
    def collect_streams_at_offset(self, offset: Any): ...
    def collect_streams(self, sha: Any): ...
    @classmethod
    def write_pack(cls, object_iter: Any, pack_write: Any, index_write: Optional[Any] = ..., object_count: Optional[Any] = ..., zlib_compression: Any = ...): ...
    @classmethod
    def create(cls, object_iter: Any, base_dir: Any, object_count: Optional[Any] = ..., zlib_compression: Any = ...): ...
