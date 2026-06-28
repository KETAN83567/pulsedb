-- Reconciliation invariant (project notes C2 Definition of Done #3):
--   raw bronze count == stg_events count + quarantine_events count
-- Proves the Silver split is lossless: every bronze row is either cleaned or
-- quarantined, never silently dropped. Passes when it returns ZERO rows.
with counts as (
    select
        (select count(*) from {{ source('raw', 'gh_events') }}) as raw_count,
        (select count(*) from {{ ref('stg_events') }}) as stg_count,
        (select count(*) from {{ ref('quarantine_events') }}) as quarantine_count
)

select *
from counts
where raw_count != stg_count + quarantine_count
