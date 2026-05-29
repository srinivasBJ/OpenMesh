CREATE TABLE IF NOT EXISTS openmesh_sessions (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL UNIQUE,
    command TEXT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    exit_code INTEGER,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_openmesh_sessions_session_id ON openmesh_sessions (session_id);
CREATE INDEX IF NOT EXISTS ix_openmesh_sessions_started_at ON openmesh_sessions (started_at);
CREATE INDEX IF NOT EXISTS ix_openmesh_sessions_status ON openmesh_sessions (status);
