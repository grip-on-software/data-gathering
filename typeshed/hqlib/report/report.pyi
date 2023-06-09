# Stubs for hqlib.report.report (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .. import domain
from ..typing import Dashboard, DateTime
from .section import Section, SectionHeader
from typing import Any, Optional, Sequence, Set, Tuple, Type

class QualityReport(domain.DomainObject):
    @staticmethod
    def domain_object_classes() -> Set[Type[domain.RequirementSubject]]: ...
    @classmethod
    def requirement_classes(cls: Any) -> Sequence[Type[domain.Requirement]]: ...
    @classmethod
    def metric_classes(cls: Any) -> Set[Type[domain.Metric]]: ...
    @classmethod
    def metric_source_classes(cls: Any) -> Set[Type[domain.MetricSource]]: ...
    def __init__(self, project: domain.Project) -> None: ...
    def title(self) -> str: ...
    def project(self) -> domain.Project: ...
    @staticmethod
    def date() -> DateTime: ...
    def sections(self) -> Sequence[Section]: ...
    def get_section(self, section_id: str) -> Optional[Section]: ...
    def dashboard(self) -> Dashboard: ...
    def metrics(self) -> Sequence[domain.Metric]: ...
    def included_metric_classes(self): ...
    def included_requirement_classes(self) -> Set[Type[domain.Requirement]]: ...
    def included_metric_source_classes(self): ...
    def included_domain_object_classes(self) -> Set[Type[domain.DomainObject]]: ...
    def products(self) -> Sequence[domain.Product]: ...
    def direct_action_needed(self) -> bool: ...
    def latest_product_version(self, product: domain.Product) -> str: ...
    def latest_product_change_date(self, product: domain.Product) -> DateTime: ...
    def vcs_id(self, product: domain.Product) -> Tuple[Optional[domain.MetricSource], str]: ...
    def sonar_id(self, product: domain.Product) -> Tuple[Optional[domain.MetricSource], str]: ...
