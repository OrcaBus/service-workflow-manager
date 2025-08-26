import logging
from typing import List

from workflow_manager.models import Analysis, Workflow, Library, Status
from workflow_manager.models.utils import create_portal_run_id
from workflow_manager_proc.domain.event import wru, arsc
from workflow_manager_proc.services.workflow_run import create_workflow_run

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

wfr_name_prefix = "umccr--automated"

def create_workflows_runs_from_analysis_run(analysis_run: arsc.AnalysisRunStateChange) -> None:
    analysis_db: Analysis = Analysis.objects.get(
        orcabus_id=analysis_run.analysis.orcabusId
    )

    # extract the libraries this analysis run is linked to
    libs_db = []
    for lib in analysis_run.libraries:
        libs_db.append(Library.objects.get(orcabus_id=lib.orcabusId))

    for workflow  in analysis_db.workflows.all():
        wru_draft = create_wru_draft(workflow, libs_db)
        wru_draft.analysisRun = _map_arsc_analysis_run_to_wru_analysis_run(analysis_run)
        wru_draft.computeEnv = analysis_run.computeEnv
        wru_draft.storageEnv = analysis_run.storageEnv
        # NOTE: initial DRAFT, so no Payload

        # create the WorkflowRun record and emit the corresponding event
        create_workflow_run(wru_draft)


def create_wru_draft(workflow: Workflow, libraries: List[Library]) -> wru.WorkflowRunUpdate:
    prid = create_portal_run_id()
    wfr_name = f"{wfr_name_prefix}--{workflow.workflow_name}--{workflow.workflow_version}--{prid}"
    # update with libraries
    wfr_libraries = []
    for lib in libraries:
        wfr_libraries.append(_map_model_library_to_wru_library(lib))

    wru_wfr = wru.WorkflowRunUpdate(
        portalRunId=prid,
        workflowRunName=wfr_name,
        status=Status.DRAFT.convention,
        workflow = _map_model_workflow_to_wru_workflow(workflow),
        libraries = wfr_libraries
    )

    # NOTE: compute/storage envs, analysis run inherited and other optional fields can be updated outside this method
    return wru_wfr


def _map_model_workflow_to_wru_workflow(wfl: Workflow) -> wru.Workflow:
    wru_wfl = wru.Workflow(
        orcabusId=wfl.orcabus_id,
        name=wfl.workflow_name,
        version=wfl.workflow_version,
        executionEngine=wfl.execution_engine
    )
    return wru_wfl


def _map_model_library_to_wru_library(lib: Library) -> wru.Library:
    wru_lib = wru.Library(
        orcabusId=lib.orcabus_id,
        libraryId=lib.library_id
    )
    return wru_lib


def _map_arsc_analysis_run_to_wru_analysis_run(run: arsc.AnalysisRunStateChange) -> wru.AnalysisRun:
    wru_anr = wru.AnalysisRun(
        orcabusId=run.orcabusId,
        name=run.analysisRunName
    )
    return wru_anr
