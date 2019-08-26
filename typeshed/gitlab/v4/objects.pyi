# Stubs for gitlab.v4.objects (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from gitlab.base import *
from gitlab.exceptions import *
from gitlab.mixins import *
from typing import Any, Dict, List, Optional, Union

VISIBILITY_PRIVATE: str
VISIBILITY_INTERNAL: str
VISIBILITY_PUBLIC: str
ACCESS_GUEST: int
ACCESS_REPORTER: int
ACCESS_DEVELOPER: int
ACCESS_MASTER: int
ACCESS_OWNER: int

class SidekiqManager(RESTManager):
    def queue_metrics(self, **kwargs: Any): ...
    def process_metrics(self, **kwargs: Any): ...
    def job_stats(self, **kwargs: Any): ...
    def compound_metrics(self, **kwargs: Any): ...



class Event(RESTObject):
    action_name: str = ...
    data: Optional[Dict[str, Union[str, List[Dict[str, str]]]]] = ...
    push_data: Dict[str, str] = ...
    author: Dict[str, str] = ...
    created_at: str = ...
    author_username: str = ...
class EventManager(ListMixin[Event], RESTManager): ...
class UserActivities(RESTObject): ...
class UserActivitiesManager(ListMixin[UserActivities], RESTManager): ...
class UserCustomAttribute(ObjectDeleteMixin, RESTObject): ...
class UserCustomAttributeManager(RetrieveMixin[UserCustomAttribute], SetMixin[UserCustomAttribute], DeleteMixin[UserCustomAttribute], RESTManager): ...
class UserEmail(ObjectDeleteMixin, RESTObject): ...
class UserEmailManager(RetrieveMixin[UserEmail], CreateMixin[UserEmail], DeleteMixin[UserEmail], RESTManager): ...
class UserEvent(Event): ...
class UserEventManager(EventManager): ...
class UserGPGKey(ObjectDeleteMixin, RESTObject): ...
class UserGPGKeyManager(RetrieveMixin[UserGPGKey], CreateMixin[UserGPGKey], DeleteMixin[UserGPGKey], RESTManager): ...
class UserKey(ObjectDeleteMixin, RESTObject): ...
class UserKeyManager(ListMixin[UserKey], CreateMixin[UserKey], DeleteMixin[UserKey], RESTManager): ...
class UserImpersonationToken(ObjectDeleteMixin, RESTObject): ...
class UserImpersonationTokenManager(NoUpdateMixin[UserImpersonationToken], RESTManager): ...
class UserProject(RESTObject): ...

class UserProjectManager(ListMixin[UserProject], CreateMixin[UserProject], RESTManager):
    def list(self, **kwargs: Any): ...

class User(SaveMixin, ObjectDeleteMixin, RESTObject):
    def block(self, **kwargs: Any): ...
    def unblock(self, **kwargs: Any): ...

class UserManager(CRUDMixin[User], RESTManager): ...
class CurrentUserEmail(ObjectDeleteMixin, RESTObject): ...
class CurrentUserEmailManager(RetrieveMixin[CurrentUserEmail], CreateMixin[CurrentUserEmail], DeleteMixin[CurrentUserEmail], RESTManager): ...
class CurrentUserGPGKey(ObjectDeleteMixin, RESTObject): ...
class CurrentUserGPGKeyManager(RetrieveMixin[CurrentUserGPGKey], CreateMixin[CurrentUserGPGKey], DeleteMixin[CurrentUserGPGKey], RESTManager): ...
class CurrentUserKey(ObjectDeleteMixin, RESTObject):
    key: str = ...
    title: str = ...
class CurrentUserKeyManager(RetrieveMixin[CurrentUserKey], CreateMixin[CurrentUserKey], DeleteMixin[CurrentUserKey], RESTManager): ...
class CurrentUser(RESTObject):
    emails: CurrentUserEmailManager = ...
    gpgkeys: CurrentUserGPGKeyManager = ...
    keys: CurrentUserKeyManager = ...

class CurrentUserManager(GetWithoutIdMixin[CurrentUser], RESTManager): ...
class ApplicationSettings(SaveMixin, RESTObject): ...

class ApplicationSettingsManager(GetWithoutIdMixin[ApplicationSettings], UpdateMixin[ApplicationSettings], RESTManager):
    def update(self, id: Optional[Any] = ..., new_data: Any = ..., **kwargs: Any) -> None: ...

class BroadcastMessage(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class BroadcastMessageManager(CRUDMixin[BroadcastMessage], RESTManager): ...
class DeployKey(RESTObject): ...
class DeployKeyManager(ListMixin[DeployKey], RESTManager): ...
class NotificationSettings(SaveMixin, RESTObject): ...
class NotificationSettingsManager(GetWithoutIdMixin[NotificationSettings], UpdateMixin[NotificationSettings], RESTManager): ...
class Dockerfile(RESTObject): ...
class DockerfileManager(RetrieveMixin[Dockerfile], RESTManager): ...
class Feature(ObjectDeleteMixin, RESTObject): ...

class FeatureManager(ListMixin[Feature], DeleteMixin[Feature], RESTManager):
    def set(self, name: Any, value: Any, feature_group: Optional[Any] = ..., user: Optional[Any] = ..., **kwargs: Any): ...

class Gitignore(RESTObject): ...
class GitignoreManager(RetrieveMixin[Gitignore], RESTManager): ...
class Gitlabciyml(RESTObject): ...
class GitlabciymlManager(RetrieveMixin[Gitlabciyml], RESTManager): ...
class GroupAccessRequest(AccessRequestMixin, ObjectDeleteMixin, RESTObject): ...
class GroupAccessRequestManager(ListMixin[GroupAccessRequest], CreateMixin[GroupAccessRequest], DeleteMixin[GroupAccessRequest], RESTManager): ...
class GroupBadge(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class GroupBadgeManager(BadgeRenderMixin, CRUDMixin[GroupBadge], RESTManager): ...
class GroupBoardList(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class GroupBoardListManager(CRUDMixin[GroupBoardList], RESTManager): ...
class GroupBoard(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class GroupBoardManager(CRUDMixin[GroupBoard], RESTManager): ...
class GroupCustomAttribute(ObjectDeleteMixin, RESTObject): ...
class GroupCustomAttributeManager(RetrieveMixin[GroupCustomAttribute], SetMixin[GroupCustomAttribute], DeleteMixin[GroupCustomAttribute], RESTManager): ...

class GroupEpicIssue(ObjectDeleteMixin, SaveMixin, RESTObject):
    def save(self, *args: Any, **kwargs: Any) -> None: ...

class GroupEpicIssueManager(ListMixin[GroupEpicIssue], CreateMixin[GroupEpicIssue], UpdateMixin[GroupEpicIssue], DeleteMixin[GroupEpicIssue], RESTManager):
    def create(self, data: Any, **kwargs: Any): ...

class GroupEpicResourceLabelEvent(RESTObject): ...
class GroupEpicResourceLabelEventManager(RetrieveMixin[GroupEpicResourceLabelEvent], RESTManager): ...
class GroupEpic(ObjectDeleteMixin, SaveMixin, RESTObject): ...
class GroupEpicManager(CRUDMixin[GroupEpic], RESTManager): ...
class GroupIssue(RESTObject): ...
class GroupIssueManager(ListMixin[GroupIssue], RESTManager): ...
class GroupMember(SaveMixin, ObjectDeleteMixin, RESTObject): ...

class GroupMemberManager(CRUDMixin[GroupMember], RESTManager):
    def all(self, **kwargs: Any): ...

class GroupMergeRequest(RESTObject): ...
class GroupMergeRequestManager(ListMixin[GroupMergeRequest], RESTManager): ...

class GroupMilestone(SaveMixin, ObjectDeleteMixin, RESTObject):
    def issues(self, **kwargs: Any): ...
    def merge_requests(self, **kwargs: Any): ...

class GroupMilestoneManager(CRUDMixin[GroupMilestone], RESTManager): ...
class GroupNotificationSettings(NotificationSettings): ...
class GroupNotificationSettingsManager(NotificationSettingsManager): ...
class GroupProject(RESTObject):
    name: str = ...
    http_url_to_repo: str = ...
class GroupProjectManager(ListMixin[GroupProject], RESTManager): ...
class GroupSubgroup(RESTObject): ...
class GroupSubgroupManager(ListMixin[GroupSubgroup], RESTManager): ...
class GroupVariable(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class GroupVariableManager(CRUDMixin[GroupVariable], RESTManager): ...

class Group(SaveMixin, ObjectDeleteMixin, RESTObject):
    def transfer_project(self, to_project_id: Any, **kwargs: Any) -> None: ...
    def search(self, scope: Any, search: Any, **kwargs: Any): ...
    def add_ldap_group_link(self, cn: Any, group_access: Any, provider: Any, **kwargs: Any) -> None: ...
    def delete_ldap_group_link(self, cn: Any, provider: Optional[Any] = ..., **kwargs: Any) -> None: ...
    def ldap_sync(self, **kwargs: Any) -> None: ...
    accessrequests: GroupAccessRequestManager = ...
    badges: GroupBadgeManager = ...
    boards: GroupBoardManager = ...
    customattributes: GroupCustomAttributeManager = ...
    epics: GroupEpicManager = ...
    issues: GroupIssueManager = ...
    members: GroupMemberManager = ...
    mergerequests: GroupMergeRequestManager = ...
    milestones: GroupMilestoneManager = ...
    notificationsettings: GroupNotificationSettingsManager = ...
    projects: GroupProjectManager = ...
    subgroups: GroupSubgroupManager = ...
    variables: GroupVariableManager = ...

class GroupManager(CRUDMixin[Group], RESTManager): ...
class Hook(ObjectDeleteMixin, RESTObject): ...
class HookManager(NoUpdateMixin[Hook], RESTManager): ...
class Issue(RESTObject): ...
class IssueManager(ListMixin[Issue], RESTManager): ...
class LDAPGroup(RESTObject): ...

class LDAPGroupManager(RESTManager):
    def list(self, **kwargs: Any): ...

class License(RESTObject): ...
class LicenseManager(RetrieveMixin[License], RESTManager): ...
class MergeRequest(RESTObject): ...
class MergeRequestManager(ListMixin[MergeRequest], RESTManager): ...

class Snippet(UserAgentDetailMixin, SaveMixin, ObjectDeleteMixin, RESTObject):
    def content(self, streamed: bool = ..., action: Optional[Any] = ..., chunk_size: int = ..., **kwargs: Any): ...

class SnippetManager(CRUDMixin[Snippet], RESTManager):
    def public(self, **kwargs: Any): ...

class Namespace(RESTObject): ...
class NamespaceManager(RetrieveMixin[Namespace], RESTManager): ...
class PagesDomain(RESTObject): ...
class PagesDomainManager(ListMixin[PagesDomain], RESTManager): ...
class ProjectRegistryRepository(ObjectDeleteMixin, RESTObject): ...
class ProjectRegistryRepositoryManager(DeleteMixin[ProjectRegistryRepository], ListMixin[ProjectRegistryRepository], RESTManager): ...
class ProjectRegistryTag(ObjectDeleteMixin, RESTObject): ...

class ProjectRegistryTagManager(DeleteMixin[ProjectRegistryTag], RetrieveMixin[ProjectRegistryTag], RESTManager):
    def delete_in_bulk(self, name_regex: str = ..., **kwargs: Any) -> None: ...

class ProjectBoardList(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectBoardListManager(CRUDMixin[ProjectBoardList], RESTManager): ...
class ProjectBoard(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectBoardManager(CRUDMixin[ProjectBoard], RESTManager): ...

class ProjectBranch(ObjectDeleteMixin, RESTObject):
    def protect(self, developers_can_push: bool = ..., developers_can_merge: bool = ..., **kwargs: Any) -> None: ...
    def unprotect(self, **kwargs: Any) -> None: ...

class ProjectBranchManager(NoUpdateMixin[ProjectBranch], RESTManager): ...
class ProjectCustomAttribute(ObjectDeleteMixin, RESTObject): ...
class ProjectCustomAttributeManager(RetrieveMixin[ProjectCustomAttribute], SetMixin[ProjectCustomAttribute], DeleteMixin[ProjectCustomAttribute], RESTManager): ...

class ProjectJob(RESTObject, RefreshMixin):
    def cancel(self, **kwargs: Any) -> None: ...
    def retry(self, **kwargs: Any) -> None: ...
    def play(self, **kwargs: Any) -> None: ...
    def erase(self, **kwargs: Any) -> None: ...
    def keep_artifacts(self, **kwargs: Any) -> None: ...
    def delete_artifacts(self, **kwargs: Any) -> None: ...
    def artifacts(self, streamed: bool = ..., action: Optional[Any] = ..., chunk_size: int = ..., **kwargs: Any): ...
    def artifact(self, path: Any, streamed: bool = ..., action: Optional[Any] = ..., chunk_size: int = ..., **kwargs: Any): ...
    def trace(self, streamed: bool = ..., action: Optional[Any] = ..., chunk_size: int = ..., **kwargs: Any): ...

class ProjectJobManager(RetrieveMixin[ProjectJob], RESTManager): ...
class ProjectCommitStatus(RESTObject, RefreshMixin): ...

class ProjectCommitStatusManager(ListMixin[ProjectCommitStatus], CreateMixin[ProjectCommitStatus], RESTManager):
    def create(self, data: Any, **kwargs: Any): ...

class ProjectCommitComment(RESTObject):
    note: str = ...
    path: Optional[str] = ...
    line: Optional[int] = ...
    line_type: Optional[str] = ...
    created_at: str = ...
    author: Dict[str, str] = ...
class ProjectCommitCommentManager(ListMixin[ProjectCommitComment], CreateMixin[ProjectCommitComment], RESTManager): ...
class ProjectCommitDiscussionNote(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectCommitDiscussionNoteManager(GetMixin[ProjectCommitDiscussionNote], CreateMixin[ProjectCommitDiscussionNote], UpdateMixin[ProjectCommitDiscussionNote], DeleteMixin[ProjectCommitDiscussionNote], RESTManager): ...
class ProjectCommitDiscussion(RESTObject): ...
class ProjectCommitDiscussionManager(RetrieveMixin[ProjectCommitDiscussion], CreateMixin[ProjectCommitDiscussion], RESTManager): ...

class ProjectCommit(RESTObject):
    def diff(self, **kwargs: Any): ...
    def cherry_pick(self, branch: Any, **kwargs: Any) -> None: ...
    def refs(self, type: str = ..., **kwargs: Any): ...
    def merge_requests(self, **kwargs: Any): ...
    id: str = ...
    comments: ProjectCommitCommentManager = ...
    discussions: ProjectCommitDiscussionManager = ...
    statuses: ProjectCommitStatusManager = ...

class ProjectCommitManager(RetrieveMixin[ProjectCommit], CreateMixin[ProjectCommit], RESTManager): ...

class ProjectEnvironment(SaveMixin, ObjectDeleteMixin, RESTObject):
    def stop(self, **kwargs: Any) -> None: ...

class ProjectEnvironmentManager(ListMixin[ProjectEnvironment], CreateMixin[ProjectEnvironment], UpdateMixin[ProjectEnvironment], DeleteMixin[ProjectEnvironment], RESTManager): ...
class ProjectKey(SaveMixin, ObjectDeleteMixin, RESTObject): ...

class ProjectKeyManager(CRUDMixin[ProjectKey], RESTManager):
    def enable(self, key_id: Any, **kwargs: Any) -> None: ...

class ProjectBadge(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectBadgeManager(BadgeRenderMixin, CRUDMixin[ProjectBadge], RESTManager): ...
class ProjectEvent(Event): ...
class ProjectEventManager(EventManager): ...
class ProjectFork(RESTObject): ...

class ProjectForkManager(CreateMixin[ProjectFork], ListMixin[ProjectFork], RESTManager):
    def list(self, **kwargs: Any): ...

class ProjectHook(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectHookManager(CRUDMixin[ProjectHook], RESTManager): ...
class ProjectIssueAwardEmoji(ObjectDeleteMixin, RESTObject): ...
class ProjectIssueAwardEmojiManager(NoUpdateMixin[ProjectIssueAwardEmoji], RESTManager): ...
class ProjectIssueNoteAwardEmoji(ObjectDeleteMixin, RESTObject): ...
class ProjectIssueNoteAwardEmojiManager(NoUpdateMixin[ProjectIssueNoteAwardEmoji], RESTManager): ...
class ProjectIssueNote(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectIssueNoteManager(CRUDMixin[ProjectIssueNote], RESTManager): ...
class ProjectIssueDiscussionNote(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectIssueDiscussionNoteManager(GetMixin[ProjectIssueDiscussionNote], CreateMixin[ProjectIssueDiscussionNote], UpdateMixin[ProjectIssueDiscussionNote], DeleteMixin[ProjectIssueDiscussionNote], RESTManager): ...
class ProjectIssueDiscussion(RESTObject): ...
class ProjectIssueDiscussionManager(RetrieveMixin[ProjectIssueDiscussion], CreateMixin[ProjectIssueDiscussion], RESTManager): ...
class ProjectIssueLink(ObjectDeleteMixin, RESTObject): ...

class ProjectIssueLinkManager(ListMixin[ProjectIssueLink], CreateMixin[ProjectIssueLink], DeleteMixin[ProjectIssueLink], RESTManager):
    def create(self, data: Any, **kwargs: Any): ...

class ProjectIssueResourceLabelEvent(RESTObject): ...
class ProjectIssueResourceLabelEventManager(RetrieveMixin[ProjectIssueResourceLabelEvent], RESTManager): ...

class ProjectIssue(UserAgentDetailMixin, SubscribableMixin, TodoMixin, TimeTrackingMixin, ParticipantsMixin, SaveMixin, ObjectDeleteMixin, RESTObject):
    def move(self, to_project_id: Any, **kwargs: Any) -> None: ...
    def related_merge_requests(self, **kwargs: Any): ...
    def closed_by(self, **kwargs: Any): ...

class ProjectIssueManager(CRUDMixin[ProjectIssue], RESTManager): ...
class ProjectMember(SaveMixin, ObjectDeleteMixin, RESTObject): ...

class ProjectMemberManager(CRUDMixin[ProjectMember], RESTManager):
    def all(self, **kwargs: Any): ...

class ProjectNote(RESTObject): ...
class ProjectNoteManager(RetrieveMixin[ProjectNote], RESTManager): ...
class ProjectNotificationSettings(NotificationSettings): ...
class ProjectNotificationSettingsManager(NotificationSettingsManager): ...
class ProjectPagesDomain(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectPagesDomainManager(CRUDMixin[ProjectPagesDomain], RESTManager): ...
class ProjectRelease(RESTObject): ...
class ProjectReleaseManager(NoUpdateMixin[ProjectRelease], RESTManager): ...

class ProjectTag(ObjectDeleteMixin, RESTObject):
    release: Any = ...
    def set_release_description(self, description: Any, **kwargs: Any) -> None: ...

class ProjectTagManager(NoUpdateMixin[ProjectTag], RESTManager): ...
class ProjectProtectedTag(ObjectDeleteMixin, RESTObject): ...
class ProjectProtectedTagManager(NoUpdateMixin[ProjectProtectedTag], RESTManager): ...
class ProjectMergeRequestApproval(SaveMixin, RESTObject): ...

class ProjectMergeRequestApprovalManager(GetWithoutIdMixin[ProjectMergeRequestApproval], UpdateMixin[ProjectMergeRequestApproval], RESTManager):
    def set_approvers(self, approver_ids: Any = ..., approver_group_ids: Any = ..., **kwargs: Any) -> None: ...

class ProjectMergeRequestAwardEmoji(ObjectDeleteMixin, RESTObject): ...
class ProjectMergeRequestAwardEmojiManager(NoUpdateMixin[ProjectMergeRequestAwardEmoji], RESTManager): ...
class ProjectMergeRequestDiff(RESTObject): ...
class ProjectMergeRequestDiffManager(RetrieveMixin[ProjectMergeRequestDiff], RESTManager): ...
class ProjectMergeRequestNoteAwardEmoji(ObjectDeleteMixin, RESTObject): ...
class ProjectMergeRequestNoteAwardEmojiManager(NoUpdateMixin[ProjectMergeRequestNoteAwardEmoji], RESTManager): ...
class ProjectMergeRequestNote(SaveMixin, ObjectDeleteMixin, RESTObject):
    id: int = ...
    author: Dict[str, str] = ...
    body: str = ...
    created_at: str = ...
class ProjectMergeRequestNoteManager(CRUDMixin[ProjectMergeRequestNote], RESTManager): ...
class ProjectMergeRequestDiscussionNote(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectMergeRequestDiscussionNoteManager(GetMixin[ProjectMergeRequestDiscussionNote], CreateMixin[ProjectMergeRequestDiscussionNote], UpdateMixin[ProjectMergeRequestDiscussionNote], DeleteMixin[ProjectMergeRequestDiscussionNote], RESTManager): ...
class ProjectMergeRequestDiscussion(SaveMixin, RESTObject): ...
class ProjectMergeRequestDiscussionManager(RetrieveMixin[ProjectMergeRequestDiscussion], CreateMixin[ProjectMergeRequestDiscussion], UpdateMixin[ProjectMergeRequestDiscussion], RESTManager): ...
class ProjectMergeRequestResourceLabelEvent(RESTObject): ...
class ProjectMergeRequestResourceLabelEventManager(RetrieveMixin[ProjectMergeRequestResourceLabelEvent], RESTManager): ...

class ProjectMergeRequest(SubscribableMixin, TodoMixin, TimeTrackingMixin, ParticipantsMixin, SaveMixin, ObjectDeleteMixin, RESTObject):
    def cancel_merge_when_pipeline_succeeds(self, **kwargs: Any) -> None: ...
    def closes_issues(self, **kwargs: Any): ...
    def commits(self, **kwargs: Any): ...
    def changes(self, **kwargs: Any): ...
    def pipelines(self, **kwargs: Any): ...
    def approve(self, sha: Optional[Any] = ..., **kwargs: Any) -> None: ...
    def unapprove(self, **kwargs: Any) -> None: ...
    def rebase(self, **kwargs: Any): ...
    def merge(self, merge_commit_message: Optional[Any] = ..., should_remove_source_branch: bool = ..., merge_when_pipeline_succeeds: bool = ..., **kwargs: Any) -> None: ...
    id: int = ...
    title: str = ...
    description: str = ...
    state: str = ...
    created_at: str = ...
    updated_at: str = ...
    source_branch: str = ...
    target_branch: str = ...
    assignee: Optional[Dict[str, str]]
    author: Dict[str, str]
    upvotes: int = ...
    downvotes: int = ...
    approvals: ProjectMergeRequestApprovalManager = ...
    awardemojis: ProjectMergeRequestAwardEmojiManager = ...
    diffs: ProjectMergeRequestDiffManager = ...
    discussions: ProjectMergeRequestDiscussionManager = ...
    notes: ProjectMergeRequestNoteManager = ...
    resourcelabelevents: ProjectMergeRequestResourceLabelEventManager = ...

class ProjectMergeRequestManager(CRUDMixin[ProjectMergeRequest], RESTManager): ...

class ProjectMilestone(SaveMixin, ObjectDeleteMixin, RESTObject):
    def issues(self, **kwargs: Any): ...
    def merge_requests(self, **kwargs: Any): ...

class ProjectMilestoneManager(CRUDMixin[ProjectMilestone], RESTManager): ...

class ProjectLabel(SubscribableMixin, SaveMixin, ObjectDeleteMixin, RESTObject):
    def save(self, *args: Any, **kwargs: Any) -> None: ...

class ProjectLabelManager(ListMixin[ProjectLabel], CreateMixin[ProjectLabel], UpdateMixin[ProjectLabel], DeleteMixin[ProjectLabel], RESTManager):
    def delete(self, name: Any, **kwargs: Any) -> None: ...

class ProjectFile(SaveMixin, ObjectDeleteMixin, RESTObject):
    def decode(self): ...
    branch: Any = ...
    commit_message: Any = ...
    file_path: Any = ...
    def save(self, *args: Any, **kwargs: Any) -> None: ...
    def delete(self, *args: Any, **kwargs: Any) -> None: ...

class ProjectFileManager(GetMixin[ProjectFile], CreateMixin[ProjectFile], UpdateMixin[ProjectFile], DeleteMixin[ProjectFile], RESTManager):
    #def get(self, file_path: Any, ref: Any, **kwargs: Any): ...
    def create(self, data: Any, **kwargs: Any): ...
    def update(self, id: Optional[Any] = ..., new_data: Any = ..., **kwargs: Any): ...
    def delete(self, name: Any, **kwargs: Any) -> None: ...
    def raw(self, file_path: Any, ref: Any, streamed: bool = ..., action: Optional[Any] = ..., chunk_size: int = ..., **kwargs: Any): ...

class ProjectPipelineJob(RESTObject): ...
class ProjectPipelineJobManager(ListMixin[ProjectPipelineJob], RESTManager): ...
class ProjectPipelineVariable(RESTObject): ...
class ProjectPipelineVariableManager(ListMixin[ProjectPipelineVariable], RESTManager): ...

class ProjectPipeline(RESTObject, RefreshMixin, ObjectDeleteMixin):
    def cancel(self, **kwargs: Any) -> None: ...
    def retry(self, **kwargs: Any) -> None: ...

class ProjectPipelineManager(RetrieveMixin[ProjectPipeline], CreateMixin[ProjectPipeline], DeleteMixin[ProjectPipeline], RESTManager):
    def create(self, data: Any, **kwargs: Any): ...

class ProjectPipelineScheduleVariable(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectPipelineScheduleVariableManager(CreateMixin[ProjectPipelineScheduleVariable], UpdateMixin[ProjectPipelineScheduleVariable], DeleteMixin[ProjectPipelineScheduleVariable], RESTManager): ...

class ProjectPipelineSchedule(SaveMixin, ObjectDeleteMixin, RESTObject):
    def take_ownership(self, **kwargs: Any) -> None: ...

class ProjectPipelineScheduleManager(CRUDMixin[ProjectPipelineSchedule], RESTManager): ...
class ProjectPushRules(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectPushRulesManager(GetWithoutIdMixin[ProjectPushRules], CreateMixin[ProjectPushRules], UpdateMixin[ProjectPushRules], DeleteMixin[ProjectPushRules], RESTManager): ...
class ProjectSnippetNoteAwardEmoji(ObjectDeleteMixin, RESTObject): ...
class ProjectSnippetNoteAwardEmojiManager(NoUpdateMixin[ProjectSnippetNoteAwardEmoji], RESTManager): ...
class ProjectSnippetNote(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectSnippetNoteManager(CRUDMixin[ProjectSnippetNote], RESTManager): ...
class ProjectSnippetAwardEmoji(ObjectDeleteMixin, RESTObject): ...
class ProjectSnippetAwardEmojiManager(NoUpdateMixin[ProjectSnippetAwardEmoji], RESTManager): ...
class ProjectSnippetDiscussionNote(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectSnippetDiscussionNoteManager(GetMixin[ProjectSnippetDiscussionNote], CreateMixin[ProjectSnippetDiscussionNote], UpdateMixin[ProjectSnippetDiscussionNote], DeleteMixin[ProjectSnippetDiscussionNote], RESTManager): ...
class ProjectSnippetDiscussion(RESTObject): ...
class ProjectSnippetDiscussionManager(RetrieveMixin[ProjectSnippetDiscussion], CreateMixin[ProjectSnippetDiscussion], RESTManager): ...

class ProjectSnippet(UserAgentDetailMixin, SaveMixin, ObjectDeleteMixin, RESTObject):
    def content(self, streamed: bool = ..., action: Optional[Any] = ..., chunk_size: int = ..., **kwargs: Any): ...

class ProjectSnippetManager(CRUDMixin[ProjectSnippet], RESTManager): ...

class ProjectTrigger(SaveMixin, ObjectDeleteMixin, RESTObject):
    def take_ownership(self, **kwargs: Any) -> None: ...

class ProjectTriggerManager(CRUDMixin[ProjectTrigger], RESTManager): ...
class ProjectUser(RESTObject): ...
class ProjectUserManager(ListMixin[ProjectUser], RESTManager): ...
class ProjectVariable(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectVariableManager(CRUDMixin[ProjectVariable], RESTManager): ...
class ProjectService(SaveMixin, ObjectDeleteMixin, RESTObject): ...

class ProjectServiceManager(GetMixin[ProjectService], UpdateMixin[ProjectService], DeleteMixin[ProjectService], RESTManager):
    def get(self, id: Any, lazy: bool = ..., **kwargs: Any): ...
    id: Any = ...
    def update(self, id: Optional[Any] = ..., new_data: Any = ..., **kwargs: Any) -> None: ...
    def available(self, **kwargs: Any): ...

class ProjectAccessRequest(AccessRequestMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectAccessRequestManager(ListMixin[ProjectAccessRequest], CreateMixin[ProjectAccessRequest], DeleteMixin[ProjectAccessRequest], RESTManager): ...
class ProjectApproval(SaveMixin, RESTObject): ...

class ProjectApprovalManager(GetWithoutIdMixin[ProjectApproval], UpdateMixin[ProjectApproval], RESTManager):
    def set_approvers(self, approver_ids: Any = ..., approver_group_ids: Any = ..., **kwargs: Any) -> None: ...

class ProjectDeployment(RESTObject): ...
class ProjectDeploymentManager(RetrieveMixin[ProjectDeployment], RESTManager): ...
class ProjectProtectedBranch(ObjectDeleteMixin, RESTObject): ...
class ProjectProtectedBranchManager(NoUpdateMixin[ProjectProtectedBranch], RESTManager): ...
class ProjectRunner(ObjectDeleteMixin, RESTObject): ...
class ProjectRunnerManager(NoUpdateMixin[ProjectRunner], RESTManager): ...
class ProjectWiki(SaveMixin, ObjectDeleteMixin, RESTObject): ...
class ProjectWikiManager(CRUDMixin[ProjectWiki], RESTManager): ...

class ProjectExport(RefreshMixin, RESTObject):
    def download(self, streamed: bool = ..., action: Optional[Any] = ..., chunk_size: int = ..., **kwargs: Any): ...

class ProjectExportManager(GetWithoutIdMixin[ProjectExport], CreateMixin[ProjectExport], RESTManager): ...
class ProjectImport(RefreshMixin, RESTObject): ...
class ProjectImportManager(GetWithoutIdMixin[ProjectImport], RESTManager): ...

class Project(SaveMixin, ObjectDeleteMixin, RESTObject):
    def repository_tree(self, path: str = ..., ref: str = ..., recursive: bool = ..., **kwargs: Any): ...
    def repository_blob(self, sha: Any, **kwargs: Any): ...
    def repository_raw_blob(self, sha: Any, streamed: bool = ..., action: Optional[Any] = ..., chunk_size: int = ..., **kwargs: Any): ...
    def repository_compare(self, from_: Any, to: Any, **kwargs: Any): ...
    def repository_contributors(self, **kwargs: Any): ...
    def repository_archive(self, sha: Optional[Any] = ..., streamed: bool = ..., action: Optional[Any] = ..., chunk_size: int = ..., **kwargs: Any): ...
    def create_fork_relation(self, forked_from_id: Any, **kwargs: Any) -> None: ...
    def delete_fork_relation(self, **kwargs: Any) -> None: ...
    def delete_merged_branches(self, **kwargs: Any) -> None: ...
    def languages(self, **kwargs: Any): ...
    def star(self, **kwargs: Any) -> None: ...
    def unstar(self, **kwargs: Any) -> None: ...
    def archive(self, **kwargs: Any) -> None: ...
    def unarchive(self, **kwargs: Any) -> None: ...
    def share(self, group_id: Any, group_access: Any, expires_at: Optional[Any] = ..., **kwargs: Any) -> None: ...
    def unshare(self, group_id: Any, **kwargs: Any) -> None: ...
    def trigger_pipeline(self, ref: Any, token: Any, variables: Any = ..., **kwargs: Any): ...
    def housekeeping(self, **kwargs: Any) -> None: ...
    def upload(self, filename: Any, filedata: Optional[Any] = ..., filepath: Optional[Any] = ..., **kwargs: Any): ...
    def snapshot(self, wiki: bool = ..., streamed: bool = ..., action: Optional[Any] = ..., chunk_size: int = ..., **kwargs: Any): ...
    def search(self, scope: Any, search: Any, **kwargs: Any): ...
    def mirror_pull(self, **kwargs: Any) -> None: ...
    def transfer_project(self, to_namespace: Any, **kwargs: Any) -> None: ...
    def artifact(self, ref_name: Any, artifact_path: Any, job: Any, streamed: bool = ..., action: Optional[Any] = ..., chunk_size: int = ..., **kwargs: Any): ...
    id: int = ...
    name: str = ...
    http_url_to_repo: str = ...
    last_activity_at: str = ... 
    default_branch: str = ...
    description: Optional[str] = ...
    avatar_url: Optional[str] = ...
    archived: bool = ...
    created_at: str = ...
    star_count: int = ...
    accessrequests: ProjectAccessRequestManager = ...
    approvals: ProjectApprovalManager = ...
    badges: ProjectBadgeManager = ...
    boards: ProjectBoardManager = ...
    branches: ProjectBranchManager = ...
    jobs: ProjectJobManager = ...
    commits: ProjectCommitManager = ...
    customattributes: ProjectCustomAttributeManager = ...
    deployments: ProjectDeploymentManager = ...
    environments: ProjectEnvironmentManager = ...
    events: ProjectEventManager = ...
    exports: ProjectExportManager = ...
    files: ProjectFileManager = ...
    forks: ProjectForkManager = ...
    hooks: ProjectHookManager = ...
    keys: ProjectKeyManager = ...
    imports: ProjectImportManager = ...
    issues: ProjectIssueManager = ...
    labels: ProjectLabelManager = ...
    members: ProjectMemberManager = ...
    mergerequests: ProjectMergeRequestManager = ...
    milestones: ProjectMilestoneManager = ...
    notes: ProjectNoteManager = ...
    notificationsettings: ProjectNotificationSettingsManager = ...
    pagesdomains: ProjectPagesDomainManager = ...
    pipelines: ProjectPipelineManager = ...
    protectedbranches: ProjectProtectedBranchManager = ...
    protectedtags: ProjectProtectedTagManager = ...
    pipelineschedules: ProjectPipelineScheduleManager = ...
    pushrules: ProjectPushRulesManager = ...
    runners: ProjectRunnerManager = ...
    services: ProjectServiceManager = ...
    snippets: ProjectSnippetManager = ...
    tags: ProjectTagManager = ...
    users: ProjectUserManager = ...
    triggers: ProjectTriggerManager = ...
    variables: ProjectVariableManager = ...
    wikis: ProjectWikiManager = ...

class ProjectManager(CRUDMixin[Project], RESTManager):
    def import_project(self, file: Any, path: Any, namespace: Optional[Any] = ..., overwrite: bool = ..., override_params: Optional[Any] = ..., **kwargs: Any): ...

class RunnerJob(RESTObject): ...
class RunnerJobManager(ListMixin[RunnerJob], RESTManager): ...
class Runner(SaveMixin, ObjectDeleteMixin, RESTObject): ...

class RunnerManager(CRUDMixin[Runner], RESTManager):
    def all(self, scope: Optional[Any] = ..., **kwargs: Any): ...
    def verify(self, token: Any, **kwargs: Any) -> None: ...

class Todo(ObjectDeleteMixin, RESTObject):
    def mark_as_done(self, **kwargs: Any) -> None: ...

class TodoManager(ListMixin[Todo], DeleteMixin[Todo], RESTManager):
    def mark_all_as_done(self, **kwargs: Any): ...

class GeoNode(SaveMixin, ObjectDeleteMixin, RESTObject):
    def repair(self, **kwargs: Any) -> None: ...
    def status(self, **kwargs: Any): ...

class GeoNodeManager(RetrieveMixin[GeoNode], UpdateMixin[GeoNode], DeleteMixin[GeoNode], RESTManager):
    def status(self, **kwargs: Any): ...
    def current_failures(self, **kwargs: Any): ...