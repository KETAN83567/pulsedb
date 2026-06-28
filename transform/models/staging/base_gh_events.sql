-- Base model (ephemeral): the single place where bronze rows are typed and
-- tagged with a data-quality verdict. stg_events and quarantine_events both
-- build on this, which guarantees: raw_count == stg_count + quarantine_count.
{{ config(materialized="ephemeral") }}

with source as (
    select * from {{ source('raw', 'gh_events') }}
),

typed as (
    select
        event_id,
        event_type,
        actor_id,
        actor_login,
        repo_id,
        repo_name,
        -- Standardize to UTC. Bronze stores TIMESTAMP WITH TIME ZONE (a UTC instant
        -- that rendered as local IST); AT TIME ZONE 'UTC' yields a naive UTC timestamp.
        created_at as created_at_tz,
        (created_at at time zone 'UTC') as created_at_utc,
        cast((created_at at time zone 'UTC') as date) as event_date,
        payload_action,
        _source_file,
        _loaded_at
    from source
)

select
    *,
    -- Data-quality contract. NULL reason == row passes and flows to stg_events;
    -- any non-null reason routes the row to quarantine_events (no silent drops).
    case
        when event_id is null then 'missing_event_id'
        when event_type is null then 'missing_event_type'
        when repo_id is null then 'missing_repo_id'
        when actor_id is null then 'missing_actor_id'
        when created_at_utc is null then 'missing_created_at'
    end as dq_reason
from typed
