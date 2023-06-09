# Stubs for hqlib.metric.environment.version_number (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ...domain import HigherIsBetterMetric
from hqlib.typing import MetricParameters, Number
from typing import Any

class SonarVersion(HigherIsBetterMetric):
    name: str = ...
    unit: str = ...
    norm_template: str = ...
    template: str = ...
    target_value: Any = ...
    perfect_value: Any = ...
    low_target_value: Any = ...
    metric_source_class: Any = ...
    def numerical_value(self) -> Number: ...
    def value(self): ...

class SonarQualityProfileVersion(HigherIsBetterMetric):
    name: str = ...
    unit: str = ...
    language_key: str = ...
    language_name: str = ...
    norm_template: str = ...
    template: str = ...
    target_value: Any = ...
    perfect_value: Any = ...
    low_target_value: Any = ...
    metric_source_class: Any = ...
    @classmethod
    def norm_template_default_values(cls: Any) -> MetricParameters: ...
    def numerical_value(self) -> Number: ...
    def value(self): ...

class SonarQualityProfileVersionJava(SonarQualityProfileVersion):
    name: str = ...
    language_key: str = ...
    language_name: str = ...
    target_value: Any = ...
    low_target_value: Any = ...

class SonarQualityProfileVersionCSharp(SonarQualityProfileVersion):
    name: str = ...
    language_key: str = ...
    language_name: str = ...
    target_value: Any = ...
    low_target_value: Any = ...

class SonarQualityProfileVersionJS(SonarQualityProfileVersion):
    name: str = ...
    language_key: str = ...
    language_name: str = ...
    target_value: Any = ...
    low_target_value: Any = ...

class SonarQualityProfileVersionWeb(SonarQualityProfileVersion):
    name: str = ...
    language_key: str = ...
    language_name: str = ...
    target_value: Any = ...
    low_target_value: Any = ...

class SonarQualityProfileVersionVisualBasic(SonarQualityProfileVersion):
    name: str = ...
    language_key: str = ...
    language_name: str = ...
    target_value: Any = ...
    low_target_value: Any = ...

class SonarQualityProfileVersionPython(SonarQualityProfileVersion):
    name: str = ...
    language_key: str = ...
    language_name: str = ...
    target_value: Any = ...
    low_target_value: Any = ...

class SonarQualityProfileVersionTypeScript(SonarQualityProfileVersion):
    name: str = ...
    language_key: str = ...
    language_name: str = ...
    target_value: Any = ...
    low_target_value: Any = ...

class SonarPluginVersion(HigherIsBetterMetric):
    name: str = ...
    unit: str = ...
    plugin_key: str = ...
    plugin_name: str = ...
    norm_template: str = ...
    template: str = ...
    target_value: Any = ...
    perfect_value: Any = ...
    low_target_value: Any = ...
    metric_source_class: Any = ...
    @classmethod
    def norm_template_default_values(cls: Any) -> MetricParameters: ...
    def numerical_value(self) -> int: ...
    def value(self): ...

class SonarPluginVersionJava(SonarPluginVersion):
    name: str = ...
    plugin_key: str = ...
    plugin_name: str = ...
    target_value: Any = ...
    low_target_value: Any = ...

class SonarPluginVersionCSharp(SonarPluginVersion):
    name: str = ...
    plugin_key: str = ...
    plugin_name: str = ...
    target_value: Any = ...
    low_target_value: Any = ...

class SonarPluginVersionJS(SonarPluginVersion):
    name: str = ...
    plugin_key: str = ...
    plugin_name: str = ...
    target_value: Any = ...
    low_target_value: Any = ...

class SonarPluginVersionWeb(SonarPluginVersion):
    name: str = ...
    plugin_key: str = ...
    plugin_name: str = ...
    target_value: Any = ...
    low_target_value: Any = ...

class SonarPluginVersionVisualBasic(SonarPluginVersion):
    name: str = ...
    plugin_key: str = ...
    plugin_name: str = ...
    target_value: Any = ...
    low_target_value: Any = ...

class SonarPluginVersionPython(SonarPluginVersion):
    name: str = ...
    plugin_key: str = ...
    plugin_name: str = ...
    target_value: Any = ...
    low_target_value: Any = ...

class SonarPluginVersionTypeScript(SonarPluginVersion):
    name: str = ...
    plugin_key: str = ...
    plugin_name: str = ...
    target_value: Any = ...
    low_target_value: Any = ...
