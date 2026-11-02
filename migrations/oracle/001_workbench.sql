-- DocLoop workbench 0.2.0. Target Oracle 19c-compatible baseline.
-- Review in a dedicated schema. Real Oracle execution has NOT been validated.
-- This file creates only workbench business tables, not LangGraph checkpoints.

CREATE TABLE dl_project (
	id VARCHAR2(32 CHAR) NOT NULL,
	name VARCHAR2(120 CHAR) NOT NULL,
	created_at VARCHAR2(40 CHAR) NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE dl_document (
	id VARCHAR2(32 CHAR) NOT NULL,
	project_id VARCHAR2(32 CHAR) NOT NULL,
	name VARCHAR2(255 CHAR) NOT NULL,
	version INTEGER NOT NULL,
	status VARCHAR2(20 CHAR) NOT NULL,
	content_hash VARCHAR2(64 CHAR) NOT NULL,
	content CLOB NOT NULL,
	created_at VARCHAR2(40 CHAR) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_dl_document_revision UNIQUE (project_id, name, version),
	FOREIGN KEY(project_id) REFERENCES dl_project (id)
);

CREATE TABLE dl_event (
	id VARCHAR2(32 CHAR) NOT NULL,
	project_id VARCHAR2(32 CHAR) NOT NULL,
	kind VARCHAR2(60 CHAR) NOT NULL,
	payload_json CLOB NOT NULL,
	created_at VARCHAR2(40 CHAR) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES dl_project (id)
);

CREATE TABLE dl_spec (
	id VARCHAR2(32 CHAR) NOT NULL,
	project_id VARCHAR2(32 CHAR) NOT NULL,
	title VARCHAR2(200 CHAR) NOT NULL,
	content CLOB NOT NULL,
	sha256 VARCHAR2(64 CHAR) NOT NULL,
	revision INTEGER NOT NULL,
	status VARCHAR2(20 CHAR) NOT NULL,
	generation_mode VARCHAR2(20 CHAR) NOT NULL,
	references_json CLOB NOT NULL,
	skill_sources_json CLOB NOT NULL,
	approved_by VARCHAR2(120 CHAR),
	approval_blob BLOB,
	approved_hash VARCHAR2(64 CHAR),
	created_at VARCHAR2(40 CHAR) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES dl_project (id)
);

CREATE TABLE dl_run (
	id VARCHAR2(32 CHAR) NOT NULL,
	project_id VARCHAR2(32 CHAR) NOT NULL,
	spec_id VARCHAR2(32 CHAR) NOT NULL,
	status VARCHAR2(20 CHAR) NOT NULL,
	"mode" VARCHAR2(20 CHAR) NOT NULL,
	result_json CLOB NOT NULL,
	created_at VARCHAR2(40 CHAR) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES dl_project (id),
	FOREIGN KEY(spec_id) REFERENCES dl_spec (id)
);
