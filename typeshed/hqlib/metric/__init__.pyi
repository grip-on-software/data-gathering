# Stubs for hqlib.metric (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .document.age import DocumentAge as DocumentAge
from .environment.failing_ci_jobs import FailingCIJobs as FailingCIJobs
from .environment.unused_ci_jobs import UnusedCIJobs as UnusedCIJobs
from .environment.version_number import SonarPluginVersionCSharp as SonarPluginVersionCSharp, SonarPluginVersionJS as SonarPluginVersionJS, SonarPluginVersionJava as SonarPluginVersionJava, SonarPluginVersionPython as SonarPluginVersionPython, SonarPluginVersionTypeScript as SonarPluginVersionTypeScript, SonarPluginVersionVisualBasic as SonarPluginVersionVisualBasic, SonarPluginVersionWeb as SonarPluginVersionWeb, SonarQualityProfileVersionCSharp as SonarQualityProfileVersionCSharp, SonarQualityProfileVersionJS as SonarQualityProfileVersionJS, SonarQualityProfileVersionJava as SonarQualityProfileVersionJava, SonarQualityProfileVersionPython as SonarQualityProfileVersionPython, SonarQualityProfileVersionTypeScript as SonarQualityProfileVersionTypeScript, SonarQualityProfileVersionVisualBasic as SonarQualityProfileVersionVisualBasic, SonarQualityProfileVersionWeb as SonarQualityProfileVersionWeb, SonarVersion as SonarVersion
from .meta_metrics import GreenMetaMetric as GreenMetaMetric, GreyMetaMetric as GreyMetaMetric, MissingMetaMetric as MissingMetaMetric, RedMetaMetric as RedMetaMetric, YellowMetaMetric as YellowMetaMetric
from .product.accessibility_metrics import AccessibilityMetric as AccessibilityMetric
from .product.aggregated_test_coverage_metrics import AggregatedTestBranchCoverage as AggregatedTestBranchCoverage, AggregatedTestCoverageReportAge as AggregatedTestCoverageReportAge, AggregatedTestStatementCoverage as AggregatedTestStatementCoverage
from .product.analysis_age import CheckmarxReportAge as CheckmarxReportAge, OWASPDependencyReportAge as OWASPDependencyReportAge, OpenVASScanReportAge as OpenVASScanReportAge, SonarAnalysisAge as SonarAnalysisAge, UnittestReportAge as UnittestReportAge
from .product.automated_regression_test_coverage_metrics import ARTBranchCoverage as ARTBranchCoverage, ARTCoverageReportAge as ARTCoverageReportAge, ARTStatementCoverage as ARTStatementCoverage
from .product.automated_regression_test_metrics import FailingRegressionTests as FailingRegressionTests, RegressionTestAge as RegressionTestAge
from .product.checkmarx_metrics import HighRiskCheckmarxAlertsMetric as HighRiskCheckmarxAlertsMetric, MediumRiskCheckmarxAlertsMetric as MediumRiskCheckmarxAlertsMetric
from .product.code_maintainability_metrics import CodeSmells as CodeSmells, MaintainabilityBugs as MaintainabilityBugs, SecurityHotspots as SecurityHotspots, Vulnerabilities as Vulnerabilities
from .product.duplication_metrics import JavaDuplication as JavaDuplication
from .product.logical_test_case_metrics import DurationOfManualLogicalTestCases as DurationOfManualLogicalTestCases, LogicalTestCasesNotApproved as LogicalTestCasesNotApproved, LogicalTestCasesNotAutomated as LogicalTestCasesNotAutomated, LogicalTestCasesNotReviewed as LogicalTestCasesNotReviewed, ManualLogicalTestCases as ManualLogicalTestCases, ManualLogicalTestCasesWithoutDuration as ManualLogicalTestCasesWithoutDuration, NumberOfManualLogicalTestCases as NumberOfManualLogicalTestCases
from .product.openvas_scan_metrics import HighRiskOpenVASScanAlertsMetric as HighRiskOpenVASScanAlertsMetric, MediumRiskOpenVASScanAlertsMetric as MediumRiskOpenVASScanAlertsMetric
from .product.owasp_dependency_metrics import HighPriorityOWASPDependencyWarnings as HighPriorityOWASPDependencyWarnings, NormalPriorityOWASPDependencyWarnings as NormalPriorityOWASPDependencyWarnings
from .product.performance.performance_metrics import PerformanceEnduranceTestErrors as PerformanceEnduranceTestErrors, PerformanceEnduranceTestWarnings as PerformanceEnduranceTestWarnings, PerformanceLoadTestErrors as PerformanceLoadTestErrors, PerformanceLoadTestWarnings as PerformanceLoadTestWarnings, PerformanceScalabilityTestErrors as PerformanceScalabilityTestErrors, PerformanceScalabilityTestWarnings as PerformanceScalabilityTestWarnings
from .product.performance.performance_test_age import PerformanceEnduranceTestAge as PerformanceEnduranceTestAge, PerformanceLoadTestAge as PerformanceLoadTestAge, PerformanceScalabilityTestAge as PerformanceScalabilityTestAge
from .product.performance.performance_test_duration import PerformanceEnduranceTestDuration as PerformanceEnduranceTestDuration, PerformanceLoadTestDuration as PerformanceLoadTestDuration, PerformanceScalabilityTestDuration as PerformanceScalabilityTestDuration
from .product.performance.performance_test_fault_percentage import PerformanceEnduranceTestFaultPercentage as PerformanceEnduranceTestFaultPercentage, PerformanceLoadTestFaultPercentage as PerformanceLoadTestFaultPercentage, PerformanceScalabilityTestFaultPercentage as PerformanceScalabilityTestFaultPercentage
from .product.size_metrics import ProductLOC as ProductLOC, TotalLOC as TotalLOC
from .product.source_code_metrics import CommentedLOC as CommentedLOC, CyclomaticComplexity as CyclomaticComplexity, LongMethods as LongMethods, ManyParameters as ManyParameters
from .product.unittest_coverage_metrics import UnittestBranchCoverage as UnittestBranchCoverage, UnittestLineCoverage as UnittestLineCoverage
from .product.unittest_metrics import FailingUnittests as FailingUnittests
from .product.user_story_metrics import UserStoriesNotApproved as UserStoriesNotApproved, UserStoriesNotReviewed as UserStoriesNotReviewed, UserStoriesWithTooFewLogicalTestCases as UserStoriesWithTooFewLogicalTestCases
from .product.version_control_metrics import UnmergedBranches as UnmergedBranches
from .product.violation_metrics import BlockerViolations as BlockerViolations, CriticalViolations as CriticalViolations, MajorViolations as MajorViolations, OJAuditErrors as OJAuditErrors, OJAuditExceptions as OJAuditExceptions, OJAuditWarnings as OJAuditWarnings, ViolationSuppressions as ViolationSuppressions
from .product.zap_scan_metrics import HighRiskZAPScanAlertsMetric as HighRiskZAPScanAlertsMetric, MediumRiskZAPScanAlertsMetric as MediumRiskZAPScanAlertsMetric
from .project.bug_metrics import OpenBugs as OpenBugs, OpenFindings as OpenFindings, OpenSecurityBugs as OpenSecurityBugs, OpenStaticSecurityAnalysisBugs as OpenStaticSecurityAnalysisBugs, QualityGate as QualityGate, TechnicalDebtIssues as TechnicalDebtIssues
from .project.last_security_test import LastSecurityTest as LastSecurityTest
from .project.process_metrics import PredictedNumberOfFinishedUserStoryPoints as PredictedNumberOfFinishedUserStoryPoints, ReadyUserStoryPoints as ReadyUserStoryPoints, UserStoriesDuration as UserStoriesDuration, UserStoriesInProgress as UserStoriesInProgress, UserStoriesWithoutPerformanceRiskAssessment as UserStoriesWithoutPerformanceRiskAssessment, UserStoriesWithoutSecurityRiskAssessment as UserStoriesWithoutSecurityRiskAssessment
from .project.project_management_metrics import ActionActivity as ActionActivity, IssueLogMetric as IssueLogMetric, OverDueActions as OverDueActions, RiskLog as RiskLog, StaleActions as StaleActions
from .team.spirit import TeamSpirit as TeamSpirit, TeamSpiritAge as TeamSpiritAge