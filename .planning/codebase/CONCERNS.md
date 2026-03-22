# Concerns & Tech Debt

> Generated: 2026-03-23
> Focus: Issues, risks, and areas needing attention

---

## Critical Issues

### Legacy Event Handler Still in Production (Not Removed)
- **File:** `app/workflow_manager_proc/services/workflow_run_legacy.py`
- **File:** `app/workflow_manager_proc/lambdas/handle_wrsc_event_legacy.py`
- **Issue:** The legacy WRSC handler is explicitly marked with a deprecation notice at line 2 of `workflow_run_legacy.py`: "We shall simply remove this module one day." It processes the old `executionservice.WorkflowRunStateChange` schema, while newer code uses the `WorkflowRunUpdate` schema. The legacy path still uses `uuid.uuid4()` for payload `refId` (line 146) rather than content-based hashing, so payloads processed through the legacy path are not deduplicated.
- **Impact:** Two incompatible code paths handle the same workflow events. The legacy path can create duplicate payloads that bypass the deduplication logic.
- **Fix approach:** Remove `workflow_run_legacy.py` and `handle_wrsc_event_legacy.py` once all callers (Stacky execution engine) have migrated to the WRU schema.

### Library Records Not Automatically Synced — On-Demand Creation as Workaround
- **Files:** `app/workflow_manager_proc/services/workflow_run.py` line 141, `app/workflow_manager_proc/services/analysis_run.py` line 93, `app/workflow_manager_proc/services/workflow_run_legacy.py` line 125
- **Issue:** All three files contain `# FIXME: remove this once library records are automatically synced`. When a library OrcaBus ID is encountered but no matching `Library` DB record exists, the code silently creates one on the fly using only the ID and library string. This bypasses the intended sync from MetadataManager via `LibraryStateChange` events.
- **Impact:** Library records created this way may have incomplete metadata. The sync mechanism it anticipates does not exist yet, so every production event relies on this workaround.
- **Fix approach:** Implement `LibraryStateChange` event consumption to pre-populate `Library` records, then remove the on-demand creation fallback.

### `executionId` Missing From WRU Event Schema
- **File:** `app/workflow_manager_proc/services/workflow_run.py` line 112
- **Issue:** `# FIXME: No executionId in the event schema. How do we do it?` — The `WorkflowRun.execution_id` field exists in the model but is never populated by the new event handler. It is only populated by the legacy handler (from the old `executionservice` schema that carries it).
- **Impact:** All new `WorkflowRun` records created via the WRU path have `execution_id = NULL`. Downstream consumers that rely on this field will receive null values.
- **Fix approach:** Decide whether `executionId` should be added to the WRU schema or derived another way (e.g., from payload data).

### RNAsum Rerun Still Uses Legacy WRSC Schema
- **File:** `app/workflow_manager/viewsets/workflow_run_action.py` line 110
- **Issue:** `# FIXME RNAsum rerun UI trigger to update legacy WRSC to WRU schema` with a GitHub issue reference (#99). The rerun action constructs its event detail using the old `executionservice` WRSC field names (`linkedLibraries`, `workflowName`, `workflowVersion`) rather than the new WRU schema.
- **Impact:** Rerun is only supported for `rnasum` workflow (`AllowedRerunWorkflow` enum contains only one value). Adding new rerun-capable workflows requires extending both the enum and the serializer map.
- **Fix approach:** Migrate `construct_rerun_eb_detail` to emit a WRU-schema event.

---

## Tech Debt

### MD5 Used for Event Identity Hashing
- **Files:** `app/workflow_manager_proc/services/workflow_run.py` lines 380–384, `app/workflow_manager_proc/services/analysis_run.py` lines 341–345, `app/workflow_manager/models/utils.py` lines 183–187
- **Issue:** Three separate hash functions all use MD5 to produce unique identifiers for WRSC events, ARSC events, and state deduplication. MD5 is cryptographically broken and, for identity/deduplication purposes, has collision risk at scale. Payload data itself uses SHA256 via `hash_payload_data` in `event_utils.py`, making the codebase inconsistent.
- **Impact:** Low immediate risk for small volumes, but inconsistent — payload data gets SHA256 while event IDs get MD5.
- **Fix approach:** Replace all three MD5 usages with SHA256 (or the same `hash_payload_data` utility).

### Status Convention Enforcement Is Deferred and Inconsistent
- **Files:** `app/workflow_manager/models/state.py` line 21, `app/workflow_manager/models/analysis_run_state.py` line 22
- **Issue:** Both `State.status` and `AnalysisRunState.status` are plain `CharField(max_length=255)` with a `TODO: How and where to enforce conventions?` comment. Convention normalization via `Status.get_convention()` is called at service layer (`workflow_run.py` line 68) but is not enforced at the model level. The `Status` enum supports open-ended "uncontrolled states" (anything not in its alias list passes through as-is), making it possible to persist arbitrary status strings.
- **Impact:** Data quality risk — status values may enter the DB in non-canonical form if a code path bypasses the service layer.
- **Fix approach:** Add a `clean()` method on `State` and `AnalysisRunState` to call `Status.get_convention()`, or use a `choices` constraint with the supported values.

### `WorkflowRunUtil` Loads All States Into Memory
- **File:** `app/workflow_manager/models/utils.py` lines 26–27, `app/workflow_manager/models/workflow_run.py` line 38
- **Issue:** `WorkflowRunUtil.__init__` calls `list(self.workflow_run.get_all_states())` which fetches all `State` rows for a run. `get_all_states()` has a `TODO: ensure order by timestamp ?` comment, and the list is not ordered. `get_latest_state()` iterates the full list to find the max timestamp rather than using a DB-side `ORDER BY`.
- **Impact:** Long-running workflows with many state records will load all states into memory on every state transition check. Ordering is not guaranteed — the `get_latest_state()` in `WorkflowRunUtil` uses a linear scan, while the method on the model directly uses `.order_by('-timestamp').first()` — two different implementations of the same concept.
- **Fix approach:** Remove `get_all_states()` from `WorkflowRunUtil`, query states with `order_by('-timestamp')` directly, and consolidate with the model's `get_latest_state()`.

### Schema Version Is a Hardcoded String Constant Per File
- **File:** `app/workflow_manager_proc/services/workflow_run.py` line 27: `WRSC_SCHEMA_VERSION = "1.0.0"`
- **File:** `app/workflow_manager_proc/services/analysis_run.py` line 24: `ARSC_SCHEMA_VERSION = "1.0.0"`
- **Issue:** Both have `TODO: set somewhere more global (and check against schema?)`. Schema versions are duplicated locally and not validated against the actual Pydantic event models they are used with.
- **Fix approach:** Move schema versions to a single shared constants module and wire them to the Pydantic models.

### Hash Verification for Incoming Events Is Acknowledged as Unverified
- **File:** `app/workflow_manager_proc/services/workflow_run.py` line 577 (test comment): `TODO: we currently don't enforce a re-calculation or verification of the hash`
- **File:** `app/workflow_manager_proc/services/workflow_run.py` lines 333–334: `TODO: allow force creation`, `TODO: include OrcaBus IDs or rely on entity values only?`
- **Issue:** The `get_wrsc_hash()` function returns an existing `id` without re-verifying it against the event fields. A caller can inject an arbitrary `id` string and it will be accepted and emitted as the event identity hash.
- **Impact:** Downstream systems that trust the event `id` as a content hash cannot verify its integrity.

### `get_all_states()` Ordering Is Not Guaranteed
- **Files:** `app/workflow_manager/models/workflow_run.py` line 38, `app/workflow_manager/models/analysis_run.py` line 32
- **Issue:** Both `WorkflowRun.get_all_states()` and `AnalysisRun.get_all_states()` return `list(self.states.all())` with `TODO: ensure order by timestamp?`. Database result ordering without an explicit `ORDER BY` is undefined.
- **Impact:** State lookups depending on this list (e.g. `WorkflowRunUtil.get_latest_state()`) may return wrong results if the DB returns records in a different order.

### `sanitize_orcabus_id` Is a Fragile String Slice
- **File:** `app/workflow_manager_proc/services/workflow_run.py` lines 30–32
- **Issue:** `sanitize_orcabus_id` does `return orcabus_id[-26:]` with `TODO: better sanitization and better location`. This relies on the OrcaBus ID prefix always being the same length. If IDs include a prefix of varying length (e.g. `lib.` vs `wfr.`), the slice will silently return the wrong substring without error.
- **Fix approach:** Strip the prefix explicitly using a known separator character rather than a fixed-length slice.

### `EventBridge` AWS Region Is Hardcoded
- **File:** `app/workflow_manager_proc/services/event_utils.py` line 11: `client = boto3.client('events', region_name='ap-southeast-2')`
- **Issue:** Region is hardcoded to `ap-southeast-2` (Sydney). Any multi-region or cross-region deployment would require a code change.
- **Fix approach:** Read region from an environment variable, e.g. `os.environ.get("AWS_DEFAULT_REGION", "ap-southeast-2")`.

### Base Settings Have `ALLOWED_HOSTS = ["*"]` and `CORS_ORIGIN_ALLOW_ALL = True`
- **File:** `app/workflow_manager/settings/base.py` lines 20, 153
- **Issue:** The base settings file (used in local and integration test environments) sets `ALLOWED_HOSTS = ["*"]` and `CORS_ORIGIN_ALLOW_ALL = True`. These are overridden in `aws.py` for production, but any environment that accidentally inherits `base.py` directly would be exposed.
- **File:** `app/workflow_manager/settings/base.py` line 18: `DEBUG = os.getenv("DJANGO_DEBUG", True)` — `DEBUG` defaults to `True` (the boolean value, not the string `"True"`; Django treats this correctly but the intent is ambiguous).

### EventBridge Schema Registry Dependency Pending Deprecation
- **File:** `app/deps/requirements.txt` line 7
- **Issue:** `# FIXME deprecate EventBridge Schema Registry https://github.com/OrcaBus/service-shared-resources/issues/10`. The packages `six==1.17.0` and `regex==2025.11.3` are required only by auto-generated EventBridge schema code in `app/workflow_manager/aws_event_bridge/executionservice/` and `app/workflow_manager/aws_event_bridge/workflowmanager/`. Both directories contain generated Python classes (`AWSEvent.py`, `Payload.py`, `LibraryRecord.py`, `WorkflowRunStateChange.py`) with `noqa: F401`, `noqa: E501` suppressions throughout.
- **Impact:** Maintaining generated binding code that is separate from the Pydantic domain models adds confusion about which schema representation is authoritative.

---

## TODOs & Incomplete Features

### WorkflowRun DRAFT Generation for AnalysisRun Not Implemented
- **File:** `app/workflow_manager_proc/services/analysis_run.py` line 136
- **Issue:** `# TODO: add WorkflowRun DRAFT generation for workflows in analysis` — this comment appears inside `finalise_analysis_run()` before calling `_create_workflow_runs_for_analysis_run()`. The latter function exists and calls `analysis_run_utils.create_workflows_runs_from_analysis_run()`, but no readsets are included in the generated WorkflowRun DRAFT events.

### AnalysisRun Status Beyond DRAFT/READY Not Supported
- **File:** `app/workflow_manager_proc/lambdas/handle_aru_event.py` lines 40–43
- **Issue:** `TODO: This currently assumes that there will be exactly one DRAFT event followed by exactly one READY event.` Only `DRAFT` and `READY` statuses are handled. The `match` statement has no `case _:` default branch — any other status passed in will silently do nothing (the `assert` on line 37 will raise first, but with a generic `AssertionError`).

### Multiple DRAFT Events Not Supported for AnalysisRun
- **File:** `app/workflow_manager_proc/lambdas/handle_aru_event.py` lines 40–43
- **Issue:** The architecture comment acknowledges that multiple DRAFT events should be supportable (like the `WorkflowRun` DRAFT update logic does), but this is explicitly deferred with no implementation.

### Duplicate READY Event Handling for AnalysisRun Relies on Implicit Guard
- **File:** `app/workflow_manager_proc/services/analysis_run.py` lines 358–362
- **Issue:** `TODO: handle the case where we receive the same READY event multiple times`. Currently protected only by the state assertion in `_finalise_analysis_run()` (it will fail if the current state is not DRAFT). This is fragile — if the DRAFT state somehow didn't exist, the `assert` would be the wrong failure mode.

### Force Recreation of WRSC/ARSC Hash Not Possible
- **Files:** `app/workflow_manager_proc/services/workflow_run.py` line 333, `app/workflow_manager_proc/services/analysis_run.py` line 307
- **Issue:** Both `get_wrsc_hash` and `get_arsc_hash` return early if `id` is already set: `TODO: allow force creation`. There is no mechanism to force a recalculation, which is also noted as unverified in tests.

### AnalysisRun Status in Fixture Is Ambiguous
- **File:** `app/workflow_manager/tests/fixtures/sim_analysis.py` line 503
- **Issue:** `valid_arun.status = "READY"  # TODO: READY or PENDING or INITIALISED ... ??` — the test fixture itself documents uncertainty about which status value is correct.

### `sim_analysis.py` Fixture Missing AnalysisRunReadset and AnalysisRunState Simulation
- **File:** `app/workflow_manager/tests/fixtures/sim_analysis.py` line 19
- **Issue:** `FIXME to also simulate AnalysisRunReadset and AnalysisRunState` — the test fixture class `TestData` is incomplete, making integration tests built on it potentially incomplete.

### Approval Context Is Commented Out Throughout Fixtures
- **File:** `app/workflow_manager/tests/fixtures/sim_analysis.py` lines 120, 237, 260, 350, 362
- **Issue:** Multiple `FIXME approval context` comments beside commented-out code for `usecase="approval"` and clinical context association. The approval workflow concept exists in the `AnalysisContext` model (`AnalysisContextUseCase`) but is not exercised in any tests.

### WorkflowRunUtil Could Be Integrated Into Model
- **File:** `app/workflow_manager/models/utils.py` line 21
- **Issue:** `TODO: this could be integrated into the WorkflowRun model class?` — `WorkflowRunUtil` is a separate utility class that holds `WorkflowRun` state transition logic, creating a split between model and behavior.

---

## Complexity Hotspots

### `_finalise_analysis_run()` — Heavy Assertion Chain
- **File:** `app/workflow_manager_proc/services/analysis_run.py` lines 141–243
- **Issue:** This 100-line function uses 10+ bare `assert` statements for business logic validation. Bare `assert`s are removed by the Python interpreter when run with `-O` (optimize flag), making them unsuitable for production validation. They also produce unhelpful `AssertionError` tracebacks rather than structured API errors.
- **Impact:** Any validation failure in this critical path raises an unhandled `AssertionError` which will propagate to the Lambda runtime as an unstructured error.
- **Safe modification:** Replace `assert` with explicit `if/raise ValueError(...)` or Django's `ValidationError`.

### `WorkflowRunUtil.transition_to()` — State Machine Logic
- **File:** `app/workflow_manager/models/utils.py` lines 56–147
- **Issue:** The state transition logic is a nested series of if-blocks without a formal state machine. Comments indicate open questions (`TODO: consider race conditions?`, `FIXME: remove once convention is enforced`). The method persists state directly inside the transition check — there is no separation between validation and persistence.
- **Impact:** Difficult to extend safely. Adding new states requires tracing through all existing branches. Race conditions are acknowledged but not mitigated (no DB-level locking or optimistic concurrency).

### `sim_analysis.py` — Large Fixture With Pairing Algorithm
- **File:** `app/workflow_manager/tests/fixtures/sim_analysis.py` (594 lines)
- **Issue:** The largest file in the codebase is a test fixture that contains a `FIXME: better pairing algorithm!` comment (line 362). The class implements a complex fluent API to set up clinical and research workflows, but several sections are commented out (approval contexts, status fields). It is both incomplete and hard to follow.

### Two Incompatible Event Schemas for WorkflowRunStateChange
- **Files:** `app/workflow_manager/aws_event_bridge/executionservice/workflowrunstatechange/` and `app/workflow_manager_proc/domain/event/wrsc.py`
- **Issue:** There are two representations of `WorkflowRunStateChange` — the old generated AWS EventBridge binding (executionservice) and the new Pydantic domain model (wrsc.py). They have different field sets (e.g., `linkedLibraries` vs `libraries`, presence of `executionId`). Both are used in production code simultaneously. The legacy handler uses the generated binding; the new handler uses Pydantic.

---

## Risks

### `assert` Statements Used as Production Business Logic Guards
- **Files:** `app/workflow_manager_proc/services/analysis_run.py` (18 asserts), `app/workflow_manager_proc/services/workflow_run_legacy.py`
- **Risk:** Python's `-O` or `-OO` flags disable `assert` statements entirely. If the Lambda runtime or deployment pipeline ever uses optimized bytecode, all these guards silently disappear. Even without `-O`, bare `AssertionError` is indistinguishable from a programming error — callers can't catch it as a business logic failure.

### Race Condition in `transition_to()` Not Mitigated
- **File:** `app/workflow_manager/models/utils.py` line 65
- **Issue:** `# TODO: consider race conditions?` — the check-then-persist pattern in `transition_to()` is not protected by a database lock or atomic compare-and-swap. Two concurrent Lambda invocations for the same `WorkflowRun` could both pass the state check and both persist the same new state, creating duplicate state records.
- **Impact:** The `unique_together = ["workflow_run", "status", "timestamp"]` constraint on `State` provides a partial guard (same status + same second would be rejected), but events with different timestamps (even by 1 second) would both succeed.

### Library Linking Only At Creation Time
- **File:** `app/workflow_manager_proc/services/workflow_run.py` line 119–120
- **Issue:** `NOTE: the library linking is expected to be established at workflow run creation time. Later changes will currently be ignored.` If a library association event arrives after the `WorkflowRun` is created, it is silently dropped.
- **Impact:** Library-to-WorkflowRun associations can be permanently incomplete with no error or alert.

### `computeEnv`/`storageEnv` Lookup in `_create_analysis_run` Will Silently Skip If Not Found
- **File:** `app/workflow_manager_proc/services/analysis_run.py` lines 110–122
- **Issue:** `RunContext.objects.get_by_keyword(...).first()` returns `None` if no matching context is found. `analysis_run.contexts.add(None)` would then silently fail or raise depending on Django version. There is no error guard around this path.

### `AnalysisRun` Duplicate Check Uses `analysis_run_name` Only
- **File:** `app/workflow_manager_proc/services/analysis_run.py` lines 68–70
- **Issue:** Duplicate detection for AnalysisRun creation filters by `analysis_run_name` only. If two different analyses share an `analysis_run_name` (possible if the name format is not globally unique), the second creation would be incorrectly rejected.

### `get_wrsc_hash()` Timestamp Is Excluded
- **File:** `app/workflow_manager_proc/services/workflow_run.py` line 344
- **Issue:** `# keywords.append(out_wrsc.timestamp.isoformat())  # ignoring time changes for now` — the timestamp is deliberately excluded from the event hash. Two WRSC events for the same run at different times but with identical other fields will produce the same hash. This is noted as intentional but means that retransmitted events cannot be distinguished from genuinely new events by hash alone.

---

*Concerns audit: 2026-03-23*
