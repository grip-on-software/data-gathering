from typing import Any, Pattern

def compile(pattern: str, flags: int = ..., **kwargs: Any) -> Pattern[str]: ...

IGNORECASE: int = ...
UNICODE: int = ...