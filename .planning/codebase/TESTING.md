# Testing Patterns
> Generated: 2026-03-23
> Focus: Test frameworks, test types, test structure, mocking, fixtures, how to run tests — covering both the Python Django application and TypeScript CDK infrastructure

---

## Overview

The codebase has two independent test suites:

| Layer | Framework | Location | Runner |
|---|---|---|---|
| Python application | Django `TestCase` + `factory_boy` + `mockito` | `app/` | `python manage.py test` |
| TypeScript CDK | Jest + `aws-cdk-lib/assertions` + `cdk-nag` | `test/` | `pnpm test` |

---

## Python Test Suite

### Framework

- **Runner**: Django's built-in test runner via `manage.py test`
- **Base class**: `django.test.TestCase` — each test runs in a transaction that is rolled back, so every test starts with a clean database
- **Factories**: `factory_boy` (`factory.django.DjangoModelFactory`) for model object creation
- **Mocking (standard library)**: `unittest.mock` — `MagicMock`, `patch`, `patch.dict`
- **Mocking (service-level)**: `mockito` (`when`, `unstub`) used in `workflow_manager_proc` service tests
- **AWS stubbing**: `botocore.stub.Stubber` for stubbing EventBridge client calls

### Run Commands

```bash
# Run entire Python test suite (from app/ directory)
python manage.py test

# Run a single test module
python manage.py test workflow_manager.tests.test_viewsets

# Run a single test class
python manage.py test workflow_manager.tests.test_viewsets.WorkflowViewSetTestCase

# Run a single test method
python manage.py test workflow_manager_proc.tests.test_workflow_run.WorkflowRunSrvUnitTests.test_create_workflow_run

# All test methods include the exact run command in their docstring
```

### Test File Organization

Tests are co-located with the application module under a `tests/` subdirectory:

```
app/
  workflow_manager/
    tests/
      __init__.py
      factories.py          # factory_boy factories for all models
      test_base.py          # tests for OrcaBusBaseModel/OrcaBusBaseManager
      test_models.py        # model-level tests (save, validation, relationships)
      test_serializers.py   # serializer unit tests
      test_utils.py         # utility and helper function tests
      test_viewsets.py      # API endpoint tests using Django test client
      fixtures/
        __init__.py
        sim_workflow.py     # fluent builder for complex workflow run scenarios
        sim_analysis.py     # fluent builder for analysis run scenarios

  workflow_manager_proc/
    tests/
      __init__.py
      case.py               # shared base test case class for proc tests
      test_analysis_run.py
      test_handle_aru_event.py
      test_handle_wrsc_event_legacy.py
      test_handle_wru_event.py
      test_payload_hash.py
      test_workflow_run.py  # comprehensive service-layer tests
      test_workflow_run_legacy.py
      test_wru.py           # Pydantic serde tests for event models
      fixtures/
        WRU_max.json        # full WorkflowRunUpdate event fixture
        WRU_min.json        # minimal WorkflowRunUpdate event fixture
        WRSC_legacy.json    # legacy schema event (used to test rejection)
        ARU_draft_max.json
        ARU_draft_min.json
        ARU_ready_max.json
        ARU_ready_min.json
        aru_test_fixtures.json
```

### Test Case Base Classes

**`django.test.TestCase`** — used directly for all `workflow_manager` tests.

**`WorkflowManagerProcUnitTestCase`** (`app/workflow_manager_proc/tests/case.py`) — shared base for `workflow_manager_proc` tests. Sets up and tears down:
- A real `botocore` EventBridge client with a `Stubber` activated
- A `patch` on `workflow_manager_proc.services.event_utils.client`
- Convenience loader methods that read JSON fixture files and validate them into Pydantic models:

```python
class WorkflowManagerProcUnitTestCase(TestCase):

    def setUp(self) -> None:
        self.events_client = botocore.session.get_session().create_client('events', region_name='ap-southeast-2')
        self.boto3_patcher = patch('workflow_manager_proc.services.event_utils.client', return_value=self.events_client)
        self.mock_boto3 = self.boto3_patcher.start()
        self.events_client_stubber = Stubber(self.events_client)
        self.events_client_stubber.activate()
        super().setUp()

    def tearDown(self) -> None:
        self.events_client_stubber.deactivate()
        self.boto3_patcher.stop()
        super().tearDown()

    def load_mock_wru_max(self):
        self.load_mock_file(rel_path="fixtures/WRU_max.json")
        mock_obj_with_envelope: wru.AWSEvent = wru.AWSEvent.model_validate(self.event)
        self.mock_wru_max: wru.WorkflowRunUpdate = mock_obj_with_envelope.detail
```

**`WorkflowManagerProcIntegrationTestCase`** — defined but empty; integration tests are not yet written.

### Factories

Location: `app/workflow_manager/tests/factories.py`

All factories use `factory.django.DjangoModelFactory`. Key patterns:
- UUIDs and IDs are generated at factory class definition time using `str(uuid.uuid4())` — this means all factory instances share the same generated UUID for that session
- `SubFactory` used for related objects: `StateFactory.workflow_run = factory.SubFactory(WorkflowRunFactory)`
- Optional FKs are set to `None` by default and configured in tests:

```python
class WorkflowRunFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WorkflowRun

    portal_run_id = f"20240130{_uid[:8]}"
    execution_id = _uid
    workflow_run_name = f"TestWorkflowRun{_uid[:8]}"
    workflow = None   # set explicitly in tests that need it

class StateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = State

    status = "READY"
    timestamp = make_aware(datetime.now())
    payload = None
    workflow_run = factory.SubFactory(WorkflowRunFactory)
```

Available factories: `WorkflowFactory`, `WorkflowRunFactory`, `PayloadFactory`, `LibraryFactory`, `StateFactory`, `AnalysisRunFactory`.

### Test Fixtures (JSON)

JSON fixtures live in `app/workflow_manager_proc/tests/fixtures/`. They represent real EventBridge event payloads. The `_max` variants contain all optional fields; the `_min` variants contain only required fields. Loading is always via the base case's `load_mock_file()` which reads relative to the test file location.

### Complex Scenario Builders

`sim_workflow.py` and `sim_analysis.py` in `app/workflow_manager/tests/fixtures/` implement a fluent builder pattern (`TestData` class) for constructing multi-object database scenarios:

```python
class TestData:
    """ImplNote: the class implemented fluent API. Chain each method calls to create the test fixture combo."""

    def __init__(self):
        self.generic_payload = PayloadFactory()
        self.libraries = [LibraryFactory(...), ...]

    def create_primary(self):
        """Create primary workflow with two executions and 4 libraries"""
        wf = WorkflowFactory(name=self.WORKFLOW_NAME + "Primary")
        wfr_1 = WorkflowRunFactory(...)
        for state in [STATUS_DRAFT, STATUS_START, STATUS_RUNNING, STATUS_FAIL]:
            StateFactory(workflow_run=wfr_1, status=state, ...)
        ...
        return self
```

### Test Structure Patterns

**setUp / tearDown pattern:**
```python
class WorkflowRunSrvUnitTests(WorkflowManagerProcUnitTestCase):

    def setUp(self) -> None:
        self.env_mock = mock.patch.dict(os.environ, {"EVENT_BUS_NAME": "FooBus"})
        self.env_mock.start()
        super().setUp()   # always call super, parent manages boto3/stubber lifecycle

    def tearDown(self) -> None:
        self.env_mock.stop()
        unstub()          # mockito cleanup
        super().tearDown()
```

**Inline object count assertions are the primary verification pattern for service tests:**
```python
def test_create_workflow_run(self):
    _ = WorkflowFactory()
    self.load_mock_wru_min()
    out_wrsc = workflow_run.create_workflow_run(self.mock_wru_min)
    self.assertIsNotNone(out_wrsc)
    self.assertEqual(Workflow.objects.count(), 1)
    self.assertEqual(WorkflowRun.objects.count(), 1)
    self.assertEqual(State.objects.count(), 1)
    self.assertEqual(Payload.objects.count(), 0)
```

**Pre/post condition comments in complex tests:**
```python
# Assert pre condition
self.assertEqual(Readset.objects.count(), 0)

workflow_run.establish_workflow_run_readsets(self.mock_wru_max, mock_wfr)

# Assert post condition
self.assertEqual(Readset.objects.count(), 4)
```

**Mockito used for service-level mocking (not `unittest.mock`):**
```python
when(workflow_run).update_workflow_run_to_new_state(...).thenReturn((False, "DOES_NOT_MATTER"))
```

**Intentional exception tests log clearly:**
```python
except ValidationError as e:
    logger.exception(f"THIS ERROR EXCEPTION IS INTENTIONAL FOR TEST. NOT ACTUAL ERROR. \n{e}")
self.assertRaises(ValidationError)
```

**Viewset tests use the Django test client directly:**
```python
class WorkflowViewSetTestCase(TestCase):
    endpoint = f"/{api_base}workflow"

    def setUp(self):
        WorkflowFactory.create_batch(size=1)

    def test_get_api(self):
        response = self.client.get(f"{self.endpoint}/")
        self.assertEqual(response.status_code, 200, 'Ok status response is expected')
```

### Mocking

**AWS EventBridge** — stubbed via `botocore.stub.Stubber`. The real boto3 client is created with botocore directly, the stubber activated, and then the service's module-level `client` reference is patched.

**Environment variables** — patched using `mock.patch.dict(os.environ, {"EVENT_BUS_NAME": "FooBus"})` in `setUp`, stopped in `tearDown`.

**Service-layer dependencies** — mocked with `mockito.when()` for coarser-grained service tests that want to isolate a single function.

### What Is Not Mocked

- The database — Django `TestCase` uses a real test database (SQLite or PostgreSQL depending on settings); all ORM calls are real
- Model validation — `full_clean()` is always called by `OrcaBusBaseModel.save()`
- Pydantic validation — event models are parsed with real `model_validate()` calls against fixture JSON

### Hash / Idempotency Tests

`test_payload_hash.py` tests the `hash_payload_data` function in `app/workflow_manager_proc/services/event_utils.py`:
- Key order in dicts must not affect the hash
- Whitespace/formatting must not affect the hash
- Array element order **does** affect the hash
- `null` values are distinct from absent keys

`test_utils.py` tests `StateUtil.create_state_hash`:
- Two `State` objects with identical field values must yield the same hash
- Changing any relevant field must change the hash
- `None` payloads are handled without error

### Coverage

No coverage tooling is configured. There is no `coverage.py` or `pytest-cov` setup. No minimum coverage threshold is enforced.

---

## TypeScript / CDK Test Suite

### Framework

- **Runner**: Jest via `pnpm test` (`tsc && jest`)
- **Config**: `jest.config.js` — roots at `<rootDir>/test`, matches `**/*.test.ts`, transforms with `ts-jest`
- **Assertion**: `aws-cdk-lib/assertions` `Template` for CloudFormation resource property assertions
- **Security scanning**: `cdk-nag` with `AwsSolutionsChecks` aspect

### Run Commands

```bash
pnpm test            # type-check + run all Jest tests
pnpm lint            # ESLint check
pnpm prettier        # Prettier format check
pnpm lint-fix        # Auto-fix lint issues
pnpm prettier-fix    # Auto-fix formatting
```

### Test Files

```
test/
  schema.test.ts      # EventBridge schema registry resource assertions
  stage.test.ts       # cdk-nag security compliance checks for the full stack
  toolchain.test.ts   # toolchain stack tests
  utils.ts            # shared test utilities (not a test file itself)
```

### CDK Snapshot / Property Test Pattern

```typescript
test('Test orcabus.workflowmanager WorkflowManagerSchemaRegistry Creation', () => {
  new WorkflowManagerSchemaRegistry(stack, 'TestWorkflowManagerSchemaRegistry');
  const template = Template.fromStack(stack);

  template.hasResourceProperties('AWS::EventSchemas::Schema', {
    SchemaName: 'orcabus.workflowmanager@WorkflowRunStateChange',
  });
});
```

### cdk-nag Security Test Pattern

```typescript
describe('cdk-nag-stateless-toolchain-stack', () => {
  const deployStack = new WorkflowManagerStack(app, 'WorkflowManagerStack', {
    ...getWorkflowManagerStackProps('PROD'),
    env: { account: '123456789', region: 'ap-southeast-2' },
  });

  Aspects.of(deployStack).add(new AwsSolutionsChecks());
  applyNagSuppression(deployStack);

  test(`cdk-nag AwsSolutions Pack errors`, () => {
    const errors = Annotations.fromStack(deployStack)
      .findError('*', Match.stringLikeRegexp('AwsSolutions-.*'))
      .map(synthesisMessageToString);
    expect(errors).toHaveLength(0);
  });
});
```

Suppression rationale is always provided as `reason` strings in `NagSuppressions.addStackSuppressions()` calls.

### CDK Test Setup

`beforeEach` creates a fresh `cdk.Stack` for isolation:
```typescript
let stack: cdk.Stack;

beforeEach(() => {
  stack = new cdk.Stack();
});
```

---

## Settings for Test Runs

Python settings module selection is controlled by `DJANGO_SETTINGS_MODULE`:
- `workflow_manager.settings.local` — local development (SQLite or local Postgres)
- `workflow_manager.settings.it` — integration test environment
- `workflow_manager.settings.aws` — deployed AWS environment

The test command (`python manage.py test`) picks up whichever settings module is active in the environment.
