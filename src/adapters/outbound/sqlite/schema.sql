-- Tables mirroring facts.ttl and one assessment-<version>.ttl (ADR 0013).
-- user_version holds the schema version; see SCHEMA_VERSION.
CREATE TABLE reports (
    report_id TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,  -- ISO 8601 UTC, sorts chronologically
    ingestion_sequence INTEGER NOT NULL UNIQUE,
    source_fingerprint TEXT UNIQUE
);
CREATE TABLE source_paths (
    report_id TEXT NOT NULL REFERENCES reports(report_id),
    path TEXT NOT NULL,
    PRIMARY KEY (report_id, path)
);
CREATE TABLE gates (
    report_id TEXT NOT NULL REFERENCES reports(report_id),
    gate_type TEXT NOT NULL,
    PRIMARY KEY (report_id, gate_type)
);
CREATE TABLE measurements (
    report_id TEXT NOT NULL,
    gate_type TEXT NOT NULL,
    metric TEXT NOT NULL,
    statistic TEXT NOT NULL,
    source TEXT NOT NULL,
    field_path TEXT NOT NULL,
    value REAL,
    unit TEXT,
    weight REAL,
    PRIMARY KEY (report_id, gate_type, metric, statistic, source),
    FOREIGN KEY (report_id, gate_type) REFERENCES gates(report_id, gate_type)
);
CREATE TABLE targets (
    version TEXT NOT NULL,
    name TEXT NOT NULL,
    metric TEXT NOT NULL,
    aggregation TEXT NOT NULL,
    unit TEXT NOT NULL,
    min REAL,
    max REAL,
    min_score REAL NOT NULL,
    PRIMARY KEY (version, name)
);
CREATE TABLE gate_assessments (
    version TEXT NOT NULL,
    report_id TEXT NOT NULL,
    gate_type TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('pass', 'fail', 'unknown')),
    baseline_report_id TEXT REFERENCES reports(report_id),
    PRIMARY KEY (version, report_id, gate_type),
    FOREIGN KEY (report_id, gate_type) REFERENCES gates(report_id, gate_type)
);
CREATE TABLE metric_assessments (
    version TEXT NOT NULL,
    report_id TEXT NOT NULL,
    gate_type TEXT NOT NULL,
    name TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('pass', 'fail', 'unknown')),
    score REAL,
    reason TEXT,
    policy_version TEXT NOT NULL,
    PRIMARY KEY (version, report_id, gate_type, name)
);
CREATE TABLE source_assessments (
    version TEXT NOT NULL,
    report_id TEXT NOT NULL,
    gate_type TEXT NOT NULL,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    excluded INTEGER NOT NULL,
    meets_target INTEGER,
    reason TEXT,
    PRIMARY KEY (version, report_id, gate_type, name, source)
);
CREATE TABLE report_assessments (
    version TEXT NOT NULL,
    report_id TEXT NOT NULL REFERENCES reports(report_id),
    previous_report_id TEXT REFERENCES reports(report_id),
    is_root INTEGER NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('pass', 'fail', 'unknown')),
    baseline_report_id TEXT REFERENCES reports(report_id),
    PRIMARY KEY (version, report_id)
);
