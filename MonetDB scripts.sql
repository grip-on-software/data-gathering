CREATE TABLE "gros"."issue" (
	"issue_id"       INTEGER     NOT NULL,
	"key"            VARCHAR(10)   NOT NULL,
	"title"          VARCHAR(250)   NOT NULL,
	"type"           INTEGER    NULL,
	"priority"       INTEGER    NULL,
	"resolution"     INTEGER    NULL,
	"fixVersion"     INTEGER    NULL,
	"bugfix"         INTEGER    NULL,
	"watchers"       INTEGER    NULL,
	"created"     TIMESTAMP  NULL,
	"updated"     TIMESTAMP  NULL,
	"description"    VARCHAR(500)  NULL,
	"duedate"        TIMESTAMP  NULL,
	"project_id"     INTEGER    NOT NULL,
	"status"         INTEGER    NULL,
	"delta_comments" VARCHAR(500)  NULL,
	"reporter"       INTEGER    NULL,
	"assignee"       INTEGER    NULL,
	"attachments"    INTEGER    NULL,
	"additional_information" VARCHAR(500)  NULL,
	"review_comments" VARCHAR(500)  NULL,
        "story_points"   INTEGER    NULL  
        --CONSTRAINT "pk_issue_id" PRIMARY KEY ("id")
);

CREATE TABLE "gros"."issuetype" (
	"id"              INTEGER     NOT NULL,
	"name"            VARCHAR(100)   NOT NULL,
	"description"     VARCHAR(500)   NULL,
        CONSTRAINT "pk_issuetype_id" PRIMARY KEY ("id")
);


CREATE TABLE "gros"."status" (
	"id"              INTEGER     NOT NULL,
	"name"            VARCHAR(100)   NOT NULL,
	"description"     VARCHAR(500)   NULL,
        CONSTRAINT "pk_status_id" PRIMARY KEY ("id")
);


CREATE TABLE "gros"."resolution" (
	"id"              INTEGER     NOT NULL,
	"name"            VARCHAR(100)   NOT NULL,
	"description"     VARCHAR(500)   NULL,
        CONSTRAINT "pk_resolution_id" PRIMARY KEY ("id")
);

CREATE TABLE "gros"."developer" (
	"id"              INTEGER     NOT NULL,
	"name"            VARCHAR(100)   NOT NULL,
	"display_name"     VARCHAR(100)   NULL,
        CONSTRAINT "pk_developer_id" PRIMARY KEY ("id")
);

CREATE TABLE "gros"."fixversion" (
	"id"              INTEGER     NOT NULL,
	"name"            VARCHAR(100)   NOT NULL,
	"description"     VARCHAR(500)   NULL,
	"release_date"    TIMESTAMP  NULL,
        CONSTRAINT "pk_fixversion_id" PRIMARY KEY ("id")
);

CREATE TABLE "gros"."priority" (
	"id"              INTEGER     NOT NULL,
	"name"            VARCHAR(100)   NOT NULL,
        CONSTRAINT "pk_priority_id" PRIMARY KEY ("id")
);

CREATE TABLE "gros"."relationshiptype" (
	"id"              INTEGER     NOT NULL,
	"name"            VARCHAR(100)   NOT NULL,
	"description"     VARCHAR(500)   NULL,
        CONSTRAINT "pk_relationshiptype_id" PRIMARY KEY ("id")
);

CREATE TABLE "gros"."issuelink" (
	"id_from"              INTEGER   NOT NULL,
	"id_to"                INTEGER   NOT NULL,
	"relationship_type"    INTEGER   NOT NULL,
        CONSTRAINT "pk_issuelink_id" PRIMARY KEY ("id_from","id_to","relationship_type")
);

CREATE TABLE "gros"."subtask" (
	"id_parent"             INTEGER   NOT NULL,
	"id_subtask"            INTEGER   NOT NULL,
        CONSTRAINT "pk_subtask_id" PRIMARY KEY ("id_parent","id_subtask")
); 
