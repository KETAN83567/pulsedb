# PulseDB — common tasks. Run `make help` for the list.
# Uses uv for everything; dbt commands run inside transform/.

DATE_HOUR ?= 2024-01-15-15

.PHONY: help setup deps ingest elementary build freshness report dashboard dagster ci-local clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

setup: ## Create venv + install all dependencies
	uv sync
	cd transform && uv run dbt deps

deps: ## Install dbt packages only
	cd transform && uv run dbt deps

ingest: ## Ingest one GH Archive hour (DATE_HOUR=YYYY-MM-DD-H). GH_MAX_EVENTS caps rows.
	uv run python ingestion/gh_archive_pipeline.py $(DATE_HOUR)

elementary: ## One-time: create Elementary observability tables
	cd transform && uv run dbt run --select elementary --profiles-dir .

build: ## Build Silver/Gold + run all tests (incl. reconciliation)
	cd transform && uv run dbt build --profiles-dir .

freshness: ## Check source freshness SLA
	cd transform && uv run dbt source freshness --profiles-dir .

report: ## Generate the Elementary HTML observability report
	cd transform && PULSEDB_DUCKDB="$$(cygpath -m "$$(cd .. && pwd)/pulsedb.duckdb" 2>/dev/null || echo "$$(cd .. && pwd)/pulsedb.duckdb")" \
		edr report --profiles-dir . --target-path ../quality/elementary_report

dashboard: ## Launch the Streamlit dashboard
	uv run streamlit run dashboard/app.py

dagster: ## Launch the Dagster UI
	uv run dagster dev -m orchestration.definitions

ci-local: ## Reproduce CI locally (capped sample build)
	GH_MAX_EVENTS=2000 $(MAKE) ingest
	$(MAKE) elementary
	$(MAKE) build
	$(MAKE) freshness

clean: ## Remove the local warehouse + dbt artifacts (keeps source)
	rm -f pulsedb.duckdb pulsedb.duckdb.wal
	rm -rf transform/target transform/dbt_packages quality/elementary_report
