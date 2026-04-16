"""
Shared helpers for viewsets: JWT/Bearer parsing, query-param filtering, and workflow grouping.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime, timezone as dt_timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import jwt
from django.db.models import Case, F, Func, IntegerField, OuterRef, Q, QuerySet, Subquery, Value, When, Window
from django.db.models.functions import Cast, Coalesce, Lower, RowNumber
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.settings import api_settings

from workflow_manager.models.analysis import Analysis
from workflow_manager.models.analysis_run import AnalysisRun
from workflow_manager.models.analysis_run_state import AnalysisRunState
from workflow_manager.models.state import State
from workflow_manager.models.workflow import Workflow
from workflow_manager.models.workflow_run import WorkflowRun
from workflow_manager.pagination import PaginationConstant

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared generic helpers
# ---------------------------------------------------------------------------


def parse_version(version_str: str) -> Optional[Tuple[int, int, int]]:
    """Parse version string in format X.Y.Z."""
    if not version_str:
        return None
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", str(version_str).strip())
    if match:
        return tuple(int(x) for x in match.groups())
    return None


def version_sort_key(version_str: str) -> Tuple[int, int, int]:
    """Return a sort key for semantic version comparison."""
    parsed = parse_version(version_str)
    return parsed if parsed is not None else (0, 0, 0)


def compare_versions(a: str, b: str) -> int:
    """Compare two version strings."""
    key_a = version_sort_key(a)
    key_b = version_sort_key(b)
    if key_a > key_b:
        return 1
    if key_a < key_b:
        return -1
    return 0


# ---------------------------------------------------------------------------
# Shared query-param helpers
# ---------------------------------------------------------------------------

# Query params handled by custom filter logic — never forwarded to ``get_by_keyword``.
NON_KEYWORD_QUERY_PARAMS = frozenset(
    {
        "start_time",
        "end_time",
        "is_ongoing",
        "status",
        api_settings.SEARCH_PARAM,
        api_settings.ORDERING_PARAM,
        PaginationConstant.PAGE,
        PaginationConstant.ROWS_PER_PAGE,
        "sortCol",
        "sortAsc",
    }
)

# Terminal latest-state statuses (matches list / stats "ongoing" definition).
WORKFLOW_RUN_TERMINATION_STATUSES: Tuple[str, ...] = (
    "FAILED",
    "ABORTED",
    "SUCCEEDED",
    "RESOLVED",
    "DEPRECATED",
)


def parse_datetime_safe(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    dt = parse_datetime(value.strip())
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_timezone.utc)
    return dt


def validate_ordering(ordering: str | None, allowed_fields: frozenset[str]) -> str | None:
    """Return *ordering* if it is in *allowed_fields*, otherwise ``None``."""
    if not ordering or not isinstance(ordering, str):
        return None
    s = ordering.strip()
    if not s or s not in allowed_fields:
        return None
    return s


def build_keyword_params(query_params) -> dict[str, list[str]]:
    """
    Build keyword args for ``get_by_keyword`` / ``get_model_fields_query``.

    Uses ``getlist`` so repeated keys stay as multiple values (e.g. several workflow ids).
    Each value is stripped; blanks are dropped. A key is omitted entirely if every value
    is blank, so we never apply ``field__iexact=''`` from params like ``?workflow_id=``.
    """
    out: dict[str, list[str]] = {}
    for k in query_params:
        if k in NON_KEYWORD_QUERY_PARAMS:
            continue
        raw = query_params.getlist(k)
        if not raw:
            continue
        values: list[str] = []
        for v in raw:
            s = v.strip() if isinstance(v, str) else str(v).strip()
            if s:
                values.append(s)
        if values:
            out[k] = values
    return out


# ---------------------------------------------------------------------------
# Search Q builders (per model)
# ---------------------------------------------------------------------------

def _workflow_run_search_q(term: str) -> Q:
    return (
        Q(orcabus_id__icontains=term)
        | Q(portal_run_id__icontains=term)
        | Q(workflow_run_name__icontains=term)
        | Q(comment__icontains=term)
        | Q(execution_id__icontains=term)
        | Q(libraries__library_id__icontains=term)
        | Q(libraries__orcabus_id__icontains=term)
        | Q(workflow__name__icontains=term)
    )


def _analysis_run_search_q(term: str) -> Q:
    return (
        Q(orcabus_id__icontains=term)
        | Q(analysis_run_name__icontains=term)
        | Q(comment__icontains=term)
        | Q(analysis__analysis_name__icontains=term)
        | Q(libraries__library_id__icontains=term)
        | Q(libraries__orcabus_id__icontains=term)
    )


def _analysis_search_q(term: str) -> Q:
    return (
        Q(orcabus_id__icontains=term)
        | Q(analysis_name__icontains=term)
        | Q(analysis_version__icontains=term)
        | Q(description__icontains=term)
    )


def _workflow_search_q(term: str) -> Q:
    return (
        Q(orcabus_id__icontains=term)
        | Q(name__icontains=term)
        | Q(version__icontains=term)
        | Q(code_version__icontains=term)
        | Q(execution_engine_pipeline_id__icontains=term)
    )


# ---------------------------------------------------------------------------
# Filtered queryset builders
# ---------------------------------------------------------------------------

def filtered_workflow_runs_queryset(
    query_params,
    *,
    termination_statuses: Iterable[str] = WORKFLOW_RUN_TERMINATION_STATUSES,
    apply_status_filter: bool = True,
    annotate_latest_state_time: bool = False,
    extra_keyword_params: Optional[dict[str, list[str]]] = None,
) -> QuerySet:
    """
    Shared queryset builder for workflow-run list, ongoing, unresolved, and stats endpoints.

    Applies keyword filters, ``start_time`` / ``end_time`` (range on latest state timestamp),
    ``is_ongoing``, optional ``status`` on the latest state, and free-text search.
    Ordering is **not** applied here; the calling viewset is responsible for sorting.

    The ``latest_state_time`` annotation uses a correlated **Subquery** (not ``Max``) so it
    never introduces a JOIN on the states table — preventing row inflation when the queryset
    is later regrouped by ``.values().annotate()`` (e.g. in stats bucket counts).
    """
    keyword_params = build_keyword_params(query_params)
    if extra_keyword_params:
        keyword_params = {**keyword_params, **extra_keyword_params}

    qs = (
        WorkflowRun.objects.get_by_keyword(**keyword_params)
        .distinct()
        .prefetch_related("states", "libraries")
        .select_related("workflow", "analysis_run")
    )

    # --- Time range on latest state timestamp ---
    start_dt = parse_datetime_safe(query_params.get("start_time", ""))
    end_dt = parse_datetime_safe(query_params.get("end_time", ""))
    status = (query_params.get("status") or "").strip()
    is_ongoing = (query_params.get("is_ongoing") or "").strip().lower()

    needs_annotation = (
        annotate_latest_state_time
        or bool(start_dt or end_dt)
        or (apply_status_filter and bool(status))
        or is_ongoing == "true"
    )
    if needs_annotation:
        latest_time_sq = (
            State.objects.filter(workflow_run=OuterRef("pk"))
            .order_by("-timestamp")
            .values("timestamp")[:1]
        )
        qs = qs.annotate(
            latest_state_time=Coalesce(
                Subquery(latest_time_sq),
                Value(datetime.min.replace(tzinfo=dt_timezone.utc)),
            )
        )

    if start_dt:
        qs = qs.filter(latest_state_time__gte=start_dt)
    if end_dt:
        qs = qs.filter(latest_state_time__lte=end_dt)

    if is_ongoing == "true":
        # Filter to runs whose *latest* state is non-terminal.  We match the
        # state row at ``latest_state_time`` and exclude terminal statuses,
        # so completed runs with earlier non-terminal states are not included.
        qs = qs.exclude(
            states__timestamp=F("latest_state_time"),
            states__status__in=termination_statuses,
        )

    if apply_status_filter and status:
        qs = qs.filter(
            states__timestamp=F("latest_state_time"),
            states__status=status.upper(),
        )

    search_term = (query_params.get(api_settings.SEARCH_PARAM) or "").strip()
    if search_term:
        qs = qs.filter(_workflow_run_search_q(search_term)).distinct()

    return qs


def filtered_analysis_runs_queryset(
    query_params,
    *,
    termination_statuses: Iterable[str] = WORKFLOW_RUN_TERMINATION_STATUSES,
    apply_status_filter: bool = True,
    annotate_latest_state_time: bool = False,
) -> QuerySet:
    """
    Shared queryset builder for analysis-run list and stats endpoints.

    Same pattern as ``filtered_workflow_runs_queryset`` but operates on
    ``AnalysisRun`` / ``AnalysisRunState``.
    """
    keyword_params = build_keyword_params(query_params)

    qs = (
        AnalysisRun.objects.get_by_keyword(**keyword_params)
        .distinct()
        .prefetch_related("libraries", "contexts", "readsets", "states")
        .select_related("analysis")
    )

    start_dt = parse_datetime_safe(query_params.get("start_time", ""))
    end_dt = parse_datetime_safe(query_params.get("end_time", ""))
    status = (query_params.get("status") or "").strip()

    needs_annotation = (
        annotate_latest_state_time
        or bool(start_dt or end_dt)
        or (apply_status_filter and bool(status))
    )
    if needs_annotation:
        latest_time_sq = (
            AnalysisRunState.objects.filter(analysis_run=OuterRef("pk"))
            .order_by("-timestamp")
            .values("timestamp")[:1]
        )
        qs = qs.annotate(
            latest_state_time=Coalesce(
                Subquery(latest_time_sq),
                Value(datetime.min.replace(tzinfo=dt_timezone.utc)),
            )
        )

    if start_dt:
        qs = qs.filter(latest_state_time__gte=start_dt)
    if end_dt:
        qs = qs.filter(latest_state_time__lte=end_dt)

    if apply_status_filter and status:
        qs = qs.filter(
            states__timestamp=F("latest_state_time"),
            states__status=status.upper(),
        )

    search_term = (query_params.get(api_settings.SEARCH_PARAM) or "").strip()
    if search_term:
        qs = qs.filter(_analysis_run_search_q(search_term)).distinct()

    return qs


def filtered_analyses_queryset(
    query_params,
    *,
    apply_status_filter: bool = True,
) -> QuerySet:
    """
    Shared queryset builder for analysis list and stats endpoints.

    Supports keyword filters, ``status`` (direct model field), and free-text search.
    """
    keyword_params = build_keyword_params(query_params)

    qs = (
        Analysis.objects.get_by_keyword(**keyword_params)
        .distinct()
        .prefetch_related("contexts", "workflows")
    )

    status = (query_params.get("status") or "").strip()
    if apply_status_filter and status:
        qs = qs.filter(status=status.upper())

    search_term = (query_params.get(api_settings.SEARCH_PARAM) or "").strip()
    if search_term:
        qs = qs.filter(_analysis_search_q(search_term)).distinct()

    return qs


def filtered_workflows_queryset(
    query_params,
    *,
    apply_status_filter: bool = True,
) -> QuerySet:
    """
    Shared queryset builder for workflow list and stats endpoints.

    Supports keyword filters, ``status`` (mapped to ``validation_state``), and free-text search.
    """
    keyword_params = build_keyword_params(query_params)

    qs = Workflow.objects.get_by_keyword(**keyword_params).distinct()

    status = (query_params.get("status") or "").strip()
    if apply_status_filter and status:
        qs = qs.filter(validation_state=status.upper())

    search_term = (query_params.get(api_settings.SEARCH_PARAM) or "").strip()
    if search_term:
        qs = qs.filter(_workflow_search_q(search_term)).distinct()

    return qs


# ---------------------------------------------------------------------------
# Workflow grouping by name (shared by workflow list and stats)
# ---------------------------------------------------------------------------


def _semver_component(position: int) -> Case:
    """Return an integer expression for the *position*-th (1-based) semver component.

    Only extracts the component when the full version string matches ``X.Y.Z``
    (all-digit parts separated by dots).  Non-semver versions fall back to 0
    for every component, exactly matching the Python ``version_sort_key``
    fallback of ``(0, 0, 0)``.
    """
    return Case(
        When(
            version__regex=r'^[0-9]+\.[0-9]+\.[0-9]+$',
            then=Cast(
                Func(
                    F("version"), Value("."), Value(str(position)),
                    function="SPLIT_PART",
                ),
                output_field=IntegerField(),
            ),
        ),
        default=Value(0),
        output_field=IntegerField(),
    )


def get_latest_workflow_ids_queryset() -> QuerySet:
    """Return a queryset of ``orcabus_id`` values for the latest workflow per name group.

    "Latest" is determined by semantic version (major.minor.patch descending),
    with ``orcabus_id`` as tie-breaker (descending). Grouping by name is
    case-insensitive, matching the Python ``get_latest_workflows_by_name_group``
    behaviour.

    The entire computation runs in the database (PostgreSQL), avoiding the need
    to materialise all ``Workflow`` rows in Python or build large ``IN (...)``
    clauses.
    """
    major = _semver_component(1)
    minor = _semver_component(2)
    patch = _semver_component(3)

    row_num = Window(
        expression=RowNumber(),
        partition_by=[Lower("name")],
        order_by=[
            major.desc(),
            minor.desc(),
            patch.desc(),
            F("orcabus_id").desc(),
        ],
    )

    return (
        Workflow.objects.annotate(row_num=row_num)
        .filter(row_num=1)
        .values_list("orcabus_id", flat=True)
    )


def get_latest_workflows_by_name_group(
    workflows: Iterable[Workflow],
) -> Tuple[List[Workflow], Dict[str, List[Workflow]]]:
    """Group workflows by name (case-insensitive), pick highest version per group.

    Version ordering uses ``version_sort_key`` (semantic ``X.Y.Z``). Among equal versions,
    stable sort keeps the first occurrence as the "latest".

    Returns:
        ``latest_list``: one ``Workflow`` per group, ordered by sorted lowercase name key.
        ``history_map``: maps each chosen latest workflow's ``orcabus_id`` to the full
        list of workflows in that name group (all versions).
    """
    grouped: dict[str, list] = defaultdict(list)
    for w in workflows:
        grouped[w.name.lower()].append(w)

    latest_list: List[Workflow] = []
    history_map: Dict[str, List[Workflow]] = {}
    for name_key in sorted(grouped.keys()):
        group = grouped[name_key]
        # Pick the highest version; when the version ties, pick the latest DB record.
        # ``orcabus_id`` is the PK and (ULID) is time-sortable, so we use it as the deterministic
        # tie-breaker.
        group.sort(
            key=lambda w: (version_sort_key(w.version), w.orcabus_id),
            reverse=True,
        )
        latest = group[0]
        latest_list.append(latest)
        history_map[latest.orcabus_id] = group

    return latest_list, history_map
