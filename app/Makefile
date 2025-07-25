.EXPORT_ALL_VARIABLES:
DJANGO_SETTINGS_MODULE = workflow_manager.settings.local
EVENT_BUS_NAME = mock-bus

DB_HOSTNAME ?= localhost
DB_PORT ?= 5432

.PHONY: test suite

install:
	@pip install -r deps/requirements-dev.txt

check: lint

lint:
	@black -t py312 --check . --exclude .venv

lint-fix:
	@black -t py312 . --exclude .venv

# alias to test suite
test: suite

suite:
	@python manage.py test

migrate:
	@python manage.py migrate

start: migrate
	@python manage.py runserver_plus 0.0.0.0:8000

clean:
	@python manage.py clean_db

mock:
	@python manage.py generate_mock_analysis_run

run-mock: reset-db migrate mock start

openapi:
	@python manage.py spectacular --format openapi > orcabus.workflowmanager.openapi.yaml

validate: openapi
	@python -m openapi_spec_validator orcabus.workflowmanager.openapi.yaml

coverage: install up migrate
	@echo $$DJANGO_SETTINGS_MODULE
	@coverage run --source='.' manage.py test

report:
	@coverage report -m
	@coverage html

up:
	@docker compose up --wait -d

down:
	@docker compose down

stop: down

ps:
	@docker compose ps

psql:
	@docker exec -e PGPASSWORD=orcabus -it orcabus_db psql -h 0.0.0.0 -d workflow_manager -U orcabus

# database operation
reset-db:
	@docker exec -e PGPASSWORD=orcabus -it orcabus_db psql -h $(DB_HOSTNAME) -U orcabus -d postgres -c "DROP DATABASE IF EXISTS workflow_manager;"
	@docker exec -e PGPASSWORD=orcabus -it orcabus_db psql -h $(DB_HOSTNAME) -U orcabus -d postgres -c "CREATE DATABASE workflow_manager;"

s3-dump-download:
	@aws s3 cp s3://orcabus-test-data-843407916570-ap-southeast-2/workflow-manager/wfm_dump.sql.gz data/wfm_dump.sql.gz

db-load-data: reset-db
	@gunzip -c data/wfm_dump.sql.gz | docker exec -i orcabus_db psql -U orcabus -d workflow_manager >/dev/null

s3-dump-download-if-not-exists:
		@if [ -f "data/wfm_dump.sql.gz" ]; then \
			echo "Using existing sql dump from './data/wfm_dump.sql.gz"; \
		else \
			echo "Downloading sql dump from './data/wfm_dump.sql.gz"; \
			$(MAKE) s3-dump-download; \
		fi

s3-load: s3-dump-download-if-not-exists db-load-data

schema-gen: schema-gen-wrsc schema-gen-arsc schema-gen-ari schema-gen-arf

schema-gen-arsc:
	@datamodel-codegen --input ../docs/events/WorkflowRunStateChange/WorkflowRunStateChange.schema.json --input-file-type jsonschema --output workflow_manager_proc/domain/event/wrsc.py

schema-gen-wrsc:
	@datamodel-codegen --input ../docs/events/AnalysisRunStateChange/AnalysisRunStateChange.schema.json --input-file-type jsonschema --output workflow_manager_proc/domain/event/arsc.py

schema-gen-ari:
	@datamodel-codegen --input ../docs/events/AnalysisRunInitiated/AnalysisRunInitiated.schema.json --input-file-type jsonschema --output workflow_manager_proc/domain/event/ari.py

schema-gen-arf:
	@datamodel-codegen --input ../docs/events/AnalysisRunFinalised/AnalysisRunFinalised.schema.json --input-file-type jsonschema --output workflow_manager_proc/domain/event/arf.py
