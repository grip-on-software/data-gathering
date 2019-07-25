# Stubs for gitlab.mixins (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from gitlab.base import RESTObjectList
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

T = TypeVar('T')

class GetMixin(Generic[T]):
    def get(self, id: Any, lazy: bool = ..., **kwargs: Any) -> T: ...

class GetWithoutIdMixin(Generic[T]):
    def get(self, id: Optional[Any] = ..., **kwargs: Any) -> T: ...

class RefreshMixin:
    def refresh(self, **kwargs: Any) -> None: ...

class ListMixin(Generic[T]):
    def list(self, **kwargs: Any) -> Union[List[T], RESTObjectList[T]]: ...

class RetrieveMixin(ListMixin[T], GetMixin[T]): ...

class CreateMixin(Generic[T]):
    def get_create_attrs(self): ...
    def create(self, data: Any, **kwargs: Any) -> T: ...

class UpdateMixin(Generic[T]):
    def get_update_attrs(self): ...
    def update(self, id: Optional[Any] = ..., new_data: Any = ..., **kwargs: Any) -> Optional[Dict[str, Any]]: ...

class SetMixin(Generic[T]):
    def set(self, key: Any, value: Any, **kwargs: Any) -> T: ...

class DeleteMixin(Generic[T]):
    def delete(self, name: Any, **kwargs: Any) -> None: ...

class CRUDMixin(GetMixin[T], ListMixin[T], CreateMixin[T], UpdateMixin, DeleteMixin): ...
class NoUpdateMixin(GetMixin[T], ListMixin[T], CreateMixin[T], DeleteMixin): ...

class SaveMixin:
    def save(self, *args: Any, **kwargs: Any) -> None: ...

class ObjectDeleteMixin:
    def delete(self, *args: Any, **kwargs: Any) -> None: ...

class UserAgentDetailMixin:
    def user_agent_detail(self, **kwargs: Any): ...

class AccessRequestMixin:
    def approve(self, access_level: Any = ..., **kwargs: Any) -> None: ...

class SubscribableMixin:
    def subscribe(self, **kwargs: Any) -> None: ...
    def unsubscribe(self, **kwargs: Any) -> None: ...

class TodoMixin:
    def todo(self, **kwargs: Any) -> None: ...

class TimeTrackingMixin:
    def time_stats(self, **kwargs: Any): ...
    def time_estimate(self, duration: Any, **kwargs: Any): ...
    def reset_time_estimate(self, **kwargs: Any): ...
    def add_spent_time(self, duration: Any, **kwargs: Any): ...
    def reset_spent_time(self, **kwargs: Any): ...

class ParticipantsMixin:
    def participants(self, **kwargs: Any): ...

class BadgeRenderMixin:
    def render(self, link_url: Any, image_url: Any, **kwargs: Any): ...
