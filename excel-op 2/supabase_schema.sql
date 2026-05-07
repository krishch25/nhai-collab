-- Run this script in your Supabase Dashboard -> "SQL Editor"
-- It will create all the necessary enterprise architecture tables for Phase 1.

CREATE TABLE IF NOT EXISTS processing_jobs (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(64) UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    job_type VARCHAR(32) NOT NULL,
    status VARCHAR(32) DEFAULT 'PENDING',
    total_rows INTEGER,
    processed_rows INTEGER DEFAULT 0,
    error_log TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    completed_at TIMESTAMP WITHOUT TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_processing_jobs_batch_id ON processing_jobs (batch_id);

CREATE TABLE IF NOT EXISTS system_metrics (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS taxonomy_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    description TEXT,
    condition_expression TEXT,
    condition_payload JSONB,
    l0 VARCHAR(255),
    l1 VARCHAR(255),
    l2 VARCHAR(255),
    source VARCHAR(64),
    created_by VARCHAR(255),
    confidence DOUBLE PRECISION,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_taxonomy_rules_name ON taxonomy_rules (name);
CREATE INDEX IF NOT EXISTS ix_taxonomy_rules_active ON taxonomy_rules (is_active);
CREATE INDEX IF NOT EXISTS ix_taxonomy_rules_l0_l1_l2 ON taxonomy_rules (l0, l1, l2);

CREATE TABLE IF NOT EXISTS raw_data (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(64),
    file_name VARCHAR(255),
    row_index INTEGER,
    raw_text TEXT,
    raw_payload JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_raw_data_batch_id ON raw_data (batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_data_raw_text ON raw_data (raw_text);
CREATE INDEX IF NOT EXISTS ix_raw_data_batch_row ON raw_data (batch_id, row_index);

CREATE TABLE IF NOT EXISTS classified_output (
    id SERIAL PRIMARY KEY,
    raw_data_id INTEGER NOT NULL REFERENCES raw_data(id) ON DELETE CASCADE,
    rule_id INTEGER REFERENCES taxonomy_rules(id) ON DELETE SET NULL,
    l0 VARCHAR(255),
    l1 VARCHAR(255),
    l2 VARCHAR(255),
    confidence DOUBLE PRECISION,
    vector_match_id VARCHAR(255),
    status VARCHAR(32) DEFAULT 'confirmed' NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_classified_output_raw_data_id ON classified_output (raw_data_id);
CREATE INDEX IF NOT EXISTS ix_classified_output_rule_id ON classified_output (rule_id);
CREATE INDEX IF NOT EXISTS ix_classified_output_status ON classified_output (status);
CREATE INDEX IF NOT EXISTS ix_classified_output_raw_rule ON classified_output (raw_data_id, rule_id);

CREATE TABLE IF NOT EXISTS rule_audit (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER NOT NULL,
    action VARCHAR(32) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    performed_by VARCHAR(255),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_rule_audit_rule_id ON rule_audit (rule_id);
