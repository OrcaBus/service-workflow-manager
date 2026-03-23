# Roadmap: service-workflow-manager RunContext Extension

**Milestone:** RunContext Enrichment
**Created:** 2026-03-23
**Granularity:** Coarse
**Coverage:** 22/22 v1 requirements mapped

## Phases

- [ ] **Phase 1: RunContext Model Enrichment** - Add `platform` enum, `data` JSONField, and `EXECUTION_MODE` use case to RunContext with safe migrations
- [ ] **Phase 2: AnalysisContext Unification** - Retire the duplicate AnalysisContext model and migrate all data and API surface to RunContext
- [ ] **Phase 3: Event Schema Evolution** - Update WRU/WRSC/ARU/ARSC schemas to structured context objects and rewire service layer handlers
- [ ] **Phase 4: ExecutionPolicy Model** - Introduce ExecutionPolicy as a first-class model for AnalysisRun operational constraints

## Phase Details

### Phase 1: RunContext Model Enrichment
**Goal**: RunContext records can express execution platform and platform-specific properties as structured, queryable fields
**Depends on**: Nothing (foundation phase)
**Requirements**: RCM-01, RCM-02, RCM-03, RCM-04, RCM-05
**Success Criteria** (what must be TRUE):
  1. A RunContext record can be created with a `platform` value of ICAV2, SEQERA, AWS_BATCH, or AWS_ECS and the value is stored and returned via the REST API
  2. A RunContext record can carry a `data` JSONField with platform-specific keys (e.g. `projectId`, `workspaceId`) and those keys survive a database round-trip unchanged
  3. RunContextUseCase choices include EXECUTION_MODE alongside COMPUTE and STORAGE, and a RunContext with `usecase=EXECUTION_MODE` can be created
  4. Two RunContext records with the same `name` and `usecase` but different `platform` values can coexist (unique constraint is `name + usecase + platform`)
  5. Existing RunContext records are unaffected by the migration — row count and all field values are preserved, with `platform` backfilled to NULL on legacy rows
**Plans:** 1 plan
Plans:
- [ ] 01-01-PLAN.md — Model enrichment (platform enum, data JSONField, EXECUTION_MODE, UniqueConstraint, migration, serializer update, tests)

### Phase 2: AnalysisContext Unification
**Goal**: AnalysisContext table is fully retired and all historical context associations are preserved under RunContext
**Depends on**: Phase 1
**Requirements**: ACU-01, ACU-02, ACU-03, ACU-04
**Success Criteria** (what must be TRUE):
  1. The `AnalysisContext` database table no longer exists after migration; `Analysis.contexts` M2M relationship points to `RunContext`
  2. All AnalysisContext records that existed before migration are present as RunContext records after migration, with no data loss (pre/post row-count assertions pass)
  3. REST API requests to the context endpoints return RunContext data; serializers and viewsets reference only RunContext
  4. The `/analysiscontext/` URL route is either removed or redirects to `/runcontext/`; no serializer references `AnalysisContext`
**Plans**: TBD

### Phase 3: Event Schema Evolution
**Goal**: WRU, WRSC, ARU, and ARSC events carry structured context objects and the service layer correctly persists platform and data to RunContext
**Depends on**: Phase 1, Phase 2
**Requirements**: EVT-01, EVT-02, EVT-03, EVT-04, EVT-05, EVT-06, EVT-07, EVT-08, EVT-09
**Success Criteria** (what must be TRUE):
  1. A WRU event with structured `computeEnv: { name, platform, data }` is processed without error and creates a RunContext record with correct `platform` and `data` field values
  2. An ARU event with structured `computeEnv`, `storageEnv`, and `executionMode` context objects creates an AnalysisRun with three associated RunContext records (one per use case)
  3. A WRSC event for a run whose context includes `platform` and `data` produces a stable, deterministic hash that incorporates both fields; duplicate WRSC events for the same run are deduplicated
  4. The ARSC hash function equivalently includes `platform` and `rfc8785(data)`; WRSC and ARSC schema versions are bumped
  5. All four Pydantic event model files (wru.py, wrsc.py, aru.py, arsc.py) are generated from updated JSON Schema files and match the structured context object shape
**Plans**: TBD

### Phase 4: ExecutionPolicy Model
**Goal**: AnalysisRun records can have operational constraint policies attached, and those policies are queryable via the REST API
**Depends on**: Phase 1
**Requirements**: EXP-01, EXP-02, EXP-03, EXP-04
**Success Criteria** (what must be TRUE):
  1. An `ExecutionPolicy` record can be created with a use case of APPROVAL or ELIGIBILITY and a `data` JSONField for policy parameters
  2. An AnalysisRun can have one or more ExecutionPolicy records associated via an M2M relationship
  3. `GET /api/v1/executionpolicy/` returns a list of ExecutionPolicy records; the endpoint requires no write permissions
  4. No model, mixin, enum value, or serializer is shared between ExecutionPolicy and RunContext — the two models are completely independent
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. RunContext Model Enrichment | 0/1 | Planned | - |
| 2. AnalysisContext Unification | 0/? | Not started | - |
| 3. Event Schema Evolution | 0/? | Not started | - |
| 4. ExecutionPolicy Model | 0/? | Not started | - |
