# Workflow Manager Service

```
Namespace: orcabus.workflowmanager
```

## CDK

See [README.md](../README.md)

## How to run Workflow Manager locally

### Ready Check

- Go to the Django project root

```
cd app
```

_If you use PyCharm then annotate this `app/` directory as "source" directory in the project structure dialog._

### Python

- Setup Python environment (conda or venv)

```
conda create -n workflow-manager python=3.12
conda activate workflow-manager
```

### Make

- At app root, perform

```
make install
make up
make ps
```

### Migration

```
python manage.py help
python manage.py showmigrations
python manage.py makemigrations
python manage.py migrate
```

### Mock Data

_^^^ please make sure to run `python manage.py migrate` first! ^^^_

#### Generate Workflow Record

```
python manage.py help generate_mock_workflow_run
    > Generate mock Workflow data into database for local development and testing
```

```
python manage.py generate_mock_workflow_run
```

#### Generate domain model for event schema

```
# generate models for all schemas
make schema-gen

# generate model for a specific schema
# AnalysisRunStateChange
schema-gen-arsc
# WorkflowRunStateChange
schema-gen-wrsc
# AnalysisRunInitiated
schema-gen-ari
# AnalysisRunFinalised
schema-gen-arf

```

#### Generate Hello Event

TODO

#### Generate Domain Event

TODO

### Run API

```
python manage.py runserver_plus
```

```
curl -s http://localhost:8000/api/v1/workflow | jq
```

Or visit in browser:

- http://localhost:8000/api/v1

### API Doc

#### Swagger

- http://localhost:8000/schema/swagger-ui/

#### OpenAPI v3

- http://localhost:8000/schema/openapi.json

## Local DB

```
make psql
```

```
workflow_manager# \l
workflow_manager# \c workflow_manager
workflow_manager# \dt
workflow_manager# \d
workflow_manager# \d workflow_manager_workflowrun
workflow_manager# select count(1) from workflow_manager_workflowrun;
workflow_manager# select * from workflow_manager_workflowrun;
workflow_manager# \q
```

## Testing

### Coverage report

```
make coverage report
```

_The HTML report is in `htmlcov/index.html`._

### Run test suite

```
make suite
```

### Unit test

```
python manage.py test workflow_manager.tests.test_viewsets.WorkflowViewSetTestCase.test_get_api
```

TODO

```
#python manage.py test workflow_manager_proc.tests.test_workflow_event.HelloEventUnitTests.test_sqs_handler
```

```
#python manage.py test workflow_manager_proc.tests.test_workflow_domain.HelloDomainUnitTests.test_marshall
```

```
#python manage.py test workflow_manager_proc.tests.test_workflow_domain.HelloDomainUnitTests.test_unmarshall
```

```
#python manage.py test workflow_manager_proc.tests.test_workflow_domain.HelloDomainUnitTests.test_aws_event_serde
```

```
#python manage.py test workflow_manager_proc.tests.test_workflow_domain.HelloDomainUnitTests.test_put_events_request_entry
```

## Tear Down

```
make down
```
