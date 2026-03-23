# Requirements: service-workflow-manager RunContext Extension

**Defined:** 2026-03-23
**Core Value:** Accurate, deduplicated state tracking of workflow and analysis runs regardless of which execution platform or project space they ran on.

## v1 Requirements

### RunContext Model Enrichment

- [ ] **RCM-01**: RunContext model exposes a `platform` field (extensible enum: ICAV2, SEQERA, AWS_BATCH, AWS_ECS) identifying the execution platform
- [ ] **RCM-02**: RunContext model exposes a `data` JSONField for platform-specific structured properties (e.g. projectId, workspaceId, jobQueue)
- [ ] **RCM-03**: RunContextUseCase enum includes `EXECUTION_MODE` alongside existing COMPUTE and STORAGE values
- [ ] **RCM-04**: RunContext unique constraint is expanded from `(name, usecase)` to `(name, usecase, platform)` via a safe migration that backfills `platform` on existing rows before tightening the constraint
- [ ] **RCM-05**: `platform` field is optional (nullable) to accommodate use cases where platform is not applicable (e.g. EXECUTION_MODE)

### AnalysisContext Unification

- [ ] **ACU-01**: `AnalysisContext` model is retired; `Analysis.contexts` M2M migrates to `RunContext` via an explicit data-preserving `RunPython` migration
- [ ] **ACU-02**: All serializers, viewsets, and URL routes referencing `AnalysisContext` are updated to use `RunContext`
- [ ] **ACU-03**: REST API consumers of `/analysiscontext/` are migrated to `/runcontext/` (or the endpoint is preserved as an alias — decision at implementation time)
- [ ] **ACU-04**: Existing `AnalysisContext` records are preserved with correct `RunContext` equivalents after migration (pre/post row-count assertions in migration)

### Event Schema Evolution

- [ ] **EVT-01**: WRU JSON Schema updated: `computeEnv`, `storageEnv`, and `executionMode` change from `Optional[str]` to structured context objects (`{ name: str, platform: str, data: object }`)
- [ ] **EVT-02**: WRSC JSON Schema updated with same structured context objects for `computeEnv`, `storageEnv`, `executionMode`
- [ ] **EVT-03**: ARU JSON Schema updated with context fields aligned with WRU (`computeEnv`, `storageEnv`, `executionMode`)
- [ ] **EVT-04**: ARSC JSON Schema updated aligned with WRSC
- [ ] **EVT-05**: Pydantic event models (wru.py, wrsc.py, aru.py, arsc.py) are regenerated from updated JSON Schema files
- [ ] **EVT-06**: `establish_workflow_run_contexts()` updated to consume structured context objects and populate `platform` and `data` on RunContext records
- [ ] **EVT-07**: ARU service layer updated to consume structured context objects on AnalysisRun creation
- [ ] **EVT-08**: WRSC event hash function updated to include `platform` and RFC8785 canonical hash of `data`; WRSC schema version bumped
- [ ] **EVT-09**: ARSC event hash function updated equivalently

### ExecutionPolicy Model

- [ ] **EXP-01**: `ExecutionPolicy` model introduced with primary key, use case field (APPROVAL, ELIGIBILITY), and `data` JSONField for policy parameters
- [ ] **EXP-02**: `AnalysisRun.policies` M2M relationship added to `ExecutionPolicy`
- [ ] **EXP-03**: REST API surface for ExecutionPolicy (read-only viewset, serializer, URL route)
- [ ] **EXP-04**: `ExecutionPolicy` shares no inheritance or use case enum values with `RunContext` — boundary enforced by model design

## v2 Requirements

### ExecutionPolicy Full Implementation

- **EXPV2-01**: ARU event schema extended to carry policy references so the external scheduler can attach policies at AnalysisRun creation time
- **EXPV2-02**: Policy enforcement logic in the AnalysisRun READY path (approval gate check before `_create_workflow_runs_for_analysis_run()`)
- **EXPV2-03**: Workflow eligibility filtering based on attached ExecutionPolicy

### RunContext Extended Querying

- **RCQV2-01**: GIN index on `RunContext.data` for high-volume key-path queries
- **RCQV2-02**: Filter API support for `data__contains` queries on RunContext list endpoint

## Out of Scope

| Feature | Reason |
|---------|--------|
| Backward-compatible union schema for old bare-string `computeEnv`/`storageEnv` | External scheduler is responsible for migration to structured objects; PROJECT.md explicitly excludes this |
| Changing WorkflowRun context cardinality | Stays one COMPUTE + one STORAGE + one EXECUTION_MODE per run |
| Policy enforcement / approval gate logic | Deferred to v2 — EXP requirements cover model stub only |
| New execution engine types on the Workflow model | Separate concern from RunContext platform |
| DLQ configuration for WRU/ARU event rules | Infrastructure change outside this service's scope; flagged as a risk to address in deployment coordination |

## Traceability

Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| RCM-01 | — | Pending |
| RCM-02 | — | Pending |
| RCM-03 | — | Pending |
| RCM-04 | — | Pending |
| RCM-05 | — | Pending |
| ACU-01 | — | Pending |
| ACU-02 | — | Pending |
| ACU-03 | — | Pending |
| ACU-04 | — | Pending |
| EVT-01 | — | Pending |
| EVT-02 | — | Pending |
| EVT-03 | — | Pending |
| EVT-04 | — | Pending |
| EVT-05 | — | Pending |
| EVT-06 | — | Pending |
| EVT-07 | — | Pending |
| EVT-08 | — | Pending |
| EVT-09 | — | Pending |
| EXP-01 | — | Pending |
| EXP-02 | — | Pending |
| EXP-03 | — | Pending |
| EXP-04 | — | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 22 ⚠️

---
*Requirements defined: 2026-03-23*
*Last updated: 2026-03-23 after initial definition*
