ALTER TABLE openmesh_events ADD COLUMN span_id VARCHAR(100);
ALTER TABLE openmesh_events ADD COLUMN parent_span_id VARCHAR(100);
ALTER TABLE openmesh_events ADD COLUMN parent_event_id VARCHAR(100);
ALTER TABLE openmesh_events ADD COLUMN root_event_id VARCHAR(100);
