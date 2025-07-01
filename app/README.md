# Workflow Manager Service

```
Namespace: orcabus.workflowmanager
```

## CDK Deployment

See [README.md](../README.md)

## Event Schema

See [README.md](../docs/events/README.md)

You can generate code binding as follows.

```bash
make schema-gen
```

## How to run Workflow Manager locally

### Ready Check

- Go to the Django project root

```bash
cd app
```

_If you use PyCharm then annotate this `app/` directory as "source" directory in the project structure dialog._

### Python

- Setup Python environment

```bash
conda create -n workflow-manager python=3.12
conda activate workflow-manager
```

### Make

- At app root, perform

```bash
make install
make up
make ps
```

### Django Basic

Learn Django (plenty of online resources) if you are new to the framework. The following are a quick starter/refresher.

```bash
python manage.py help
python manage.py showmigrations
python manage.py makemigrations
python manage.py migrate

python manage.py help generate_mock_workflow_run
    > Generate mock Workflow data into database for local development and testing
```

We wrap these Django management commands into `Makefile` for local dev routine purpose.

### Mock Data

```bash
make migrate
make mock
```

### Run API

```bash
make start
```

```bash
curl -s http://localhost:8000/api/v1/workflow | jq
```

Or visit in browser:

- http://localhost:8000/api/v1

### API Doc

- http://localhost:8000/schema/swagger-ui/
- http://localhost:8000/schema/openapi.json

## Local DB

```bash
make psql
```

```bash
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

## Tear Down

```
make down
```
