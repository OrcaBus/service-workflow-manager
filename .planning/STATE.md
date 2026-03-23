# Project State: service-workflow-manager RunContext Extension

**Last updated:** 2026-03-23
**Updated by:** roadmapper (initial creation)

---

## Project Reference

**Core value:** Accurate, deduplicated state tracking of workflow and analysis runs regardless of which execution platform or project space they ran on.

**Current focus:** RunContext enrichment — replacing opaque bare-string execution environment references with structured, platform-typed context objects across the Django model, data migration, event schemas, and a new ExecutionPolicy model.

---

## Current Position

**Milestone:** RunContext Extension
**Phase:** Not started
**Plan:** None
**Status:** Roadmap created — awaiting phase planning

**Progress bar:**
```
Phase 1 [          ] 0%
Phase 2 [          ] 0%
Phase 3 [          ] 0%
Phase 4 [          ] 0%
```

---

## Performance Metrics

**Plans completed:** 0
**Requirements satisfied:** 0 / 22
**Phases completed:** 0 / 4

---

## Accumulated Context

### Key Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| `platform` as TextChoices enum | Queryable, validated, self-documenting; consistent with existing ExecutionEngine pattern | Pending |
| `AnalysisContext` unified into `RunContext` | Structurally identical models; eliminates duplication that compounds with every extension | Pending |
| Event schema uses structured context objects | Platform + project/space cannot be expressed in a single opaque string | Pending |
| `ExecutionPolicy` as separate model from `RunContext` | Operational constraints are orthogonal to execution environment | Pending |
| Three-step unique constraint migration | Prevents NULL ambiguity from creating silent duplicates during backfill window | Pending |

### Blockers

None.

### Open Questions

- **Unique constraint backfill strategy:** Should existing opaque-name RunContext rows be backfilled with a specific `platform` value or left as NULL? This governs the `get_or_create` lookup strategy in `establish_workflow_run_contexts()` after Phase 3. Decide at Phase 1 planning.
- **AnalysisContext REST API consumers:** Are any external OrcaBus services holding `anx.` prefixed IDs and using them programmatically? Audit required before Phase 2 migration planning.
- **`datamodel-code-generator` Makefile flags:** Specific flags and target name need verification against the project Makefile before Phase 3 JSON Schema updates.

### Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| AnalysisContext M2M data destroyed if table dropped before data transfer | Low (with explicit RunPython migration) | High | Write explicit RunPython migration with row-count assertions; never rely on auto-generated DeleteModel migration order |
| EventBridge schema cut-over window breaks Lambda handlers | Medium (cross-service coordination) | High | Deploy permissive consumer (this service) before upstream scheduler deploys structured producer |
| WRSC/ARSC hash changes break downstream deduplication | Low (with schema version bump) | Medium | Bump WRSC_SCHEMA_VERSION; add regression test with known-fixture hash values |
| `null` vs `{}` JSONField ambiguity corrupts hash inputs | Low (with clean() enforcement) | Medium | Enforce `data={}` → `data=None` normalisation in RunContext.clean() at model creation time |

---

## Session Continuity

**Last session:** 2026-03-23 — Project initialized, research completed, roadmap created.

**To resume:**
1. Read this file for current position
2. Read `.planning/ROADMAP.md` for phase structure
3. Run `/gsd:plan-phase 1` to begin Phase 1 planning

**Files of interest:**
- `.planning/ROADMAP.md` — phase structure and success criteria
- `.planning/REQUIREMENTS.md` — full requirement list with traceability
- `.planning/research/SUMMARY.md` — architecture approach, pitfalls, and phase ordering rationale
- `.planning/research/ARCHITECTURE.md` — migration sequences and data flow diagrams
- `.planning/research/PITFALLS.md` — detailed pitfall mitigations
