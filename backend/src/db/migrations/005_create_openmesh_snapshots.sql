CREATE TABLE IF NOT EXISTS openmesh_snapshots (
    id VARCHAR PRIMARY KEY,
    snapshot_id VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL,
    event_count INTEGER NOT NULL DEFAULT 0,
    trace_count INTEGER NOT NULL DEFAULT 0,
    session_count INTEGER NOT NULL DEFAULT 0,
    node_count INTEGER NOT NULL DEFAULT 0,
    edge_count INTEGER NOT NULL DEFAULT 0,
    counts_json JSON NOT NULL DEFAULT '{}',
    graph_stats_json JSON NOT NULL DEFAULT '{}',
    ecosystem_stats_json JSON NOT NULL DEFAULT '{}',
    snapshot_json JSON NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS ix_openmesh_snapshots_snapshot_id
    ON openmesh_snapshots (snapshot_id);

CREATE INDEX IF NOT EXISTS ix_openmesh_snapshots_created_at
    ON openmesh_snapshots (created_at);
