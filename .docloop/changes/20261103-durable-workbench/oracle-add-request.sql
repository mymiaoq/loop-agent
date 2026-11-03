-- 新增请求去重表；仅Oracle存储需要。未在真实Oracle执行。
CREATE TABLE dl_request (
	id VARCHAR2(64 CHAR) NOT NULL,
	project_id VARCHAR2(32 CHAR) NOT NULL,
	spec_id VARCHAR2(32 CHAR) NOT NULL,
	payload_hash VARCHAR2(64 CHAR) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES dl_project (id),
	FOREIGN KEY(spec_id) REFERENCES dl_spec (id)
);
