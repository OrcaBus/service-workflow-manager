import django

django.setup()

# --- keep ^^^ at top of the module
import logging
import datetime
from workflow_manager.models.analysis_run import AnalysisRun
from workflow_manager_proc.services import emit_analysis_run_state_change, create_analysis_run
from workflow_manager_proc.domain.event import ari, arsc

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Parameters:
        event: JSON event conform to <glue>.AnalysisRunRequest
        context: ignored for now (only used to conform to Lambda handler conventions)
    Procedure:
        - Unpack AWS event
        - create new State for AnalysisRun if required
        - relay the state change as WorkflowManager ARSC event if applicable
    """
    logger.info(f"Processing {event}, {context}")

    # remove the AWSEvent wrapper from our ARI event
    input_event: ari.AWSEvent = ari.AWSEvent.model_validate_json(event)
    # get the actual AnalysisRunRequest
    analysis_run_init: ari.AnalysisRunInitiated = input_event.detail

    # check state list
    analysis_run_db: AnalysisRun = create_analysis_run.handler(analysis_run_init.model_dump_json(), None)
    if analysis_run_db:
        # new AnalysisRun created, we can emit the ARSC
        arsc_object: arsc.AnalysisRunStateChange = map_analysis_run_to_arsc(analysis_run_db)
        logger.info("Emitting ARSC.")
        emit_analysis_run_state_change.handler(arsc_object.model_dump_json(), None)
    else:
        logger.info(f"AnalysisRun not created. No event to emit.")

    logger.info(f"{__name__} done.")


def map_analysis_run_to_arsc(analysis_run: AnalysisRun) -> arsc.AnalysisRunStateChange:
    lib_list = list()
    for l in analysis_run.libraries.all():
        lib_list.append(arsc.Library(
            orcabusId=l.orcabus_id,
            libraryId=l.library_id
        ))

    arsc_object = arsc.AnalysisRunStateChange(
        orcabusId=analysis_run.orcabus_id,
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        status=analysis_run.status,
        analysisRunName=analysis_run.analysis_run_name,
        analysis=arsc.Analysis(
            orcabusId=analysis_run.analysis.orcabus_id,
            name=analysis_run.analysis.analysis_name,
            version=analysis_run.analysis.analysis_version
        ),
        libraries=lib_list,
    )
    return arsc_object
