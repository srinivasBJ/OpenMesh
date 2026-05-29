CREATE TABLE IF NOT EXISTS openmesh_events (
    id VARCHAR PRIMARY KEY,
    event_id VARCHAR(100) NOT NULL UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    trace_id VARCHAR(100) NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    source_json JSON NOT NULL,
    target_json JSON,
    payload_json JSON NOT NULL,
    metrics_json JSON NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'info',
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_openmesh_events_event_id ON openmesh_events (event_id);
CREATE INDEX IF NOT EXISTS ix_openmesh_events_event_type ON openmesh_events (event_type);
CREATE INDEX IF NOT EXISTS ix_openmesh_events_timestamp ON openmesh_events (timestamp);
CREATE INDEX IF NOT EXISTS ix_openmesh_events_trace_id ON openmesh_events (trace_id);
CREATE INDEX IF NOT EXISTS ix_openmesh_events_session_id ON openmesh_events (session_id);
