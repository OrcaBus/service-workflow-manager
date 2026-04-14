from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from workflow_manager.models.workflow import Workflow
from workflow_manager.serializers.base import version_sort_key


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
        group.sort(key=lambda w: version_sort_key(w.version), reverse=True)
        latest = group[0]
        latest_list.append(latest)
        history_map[latest.orcabus_id] = group

    return latest_list, history_map
