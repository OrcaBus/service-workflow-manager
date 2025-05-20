# import django

# django.setup()

# # --- keep ^^^ at top of the module
import datetime
import logging

from django.db import transaction
from django.db.models.query import QuerySet

from workflow_manager_proc.domain.event import ari
from workflow_manager.models import (
    AnalysisRun,
    Analysis,
    Library,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ASSOCIATION_STATUS = "ACTIVE"


def sanitize_orcabus_id(orcabus_id: str) -> str:
    # TODO: better sanitization and better location
    return orcabus_id[-26:]


@transaction.atomic
def handler(event, context):
    """
    Parameters:
        event: JSON event conform to <executionservice>.AnalysisRunStateChange
        context: ignored for now (only used to conform to Lambda handler conventions)
    Procedure:
        - check whether a corresponding Analysis record exists (it should according to the pre-planning approach)
            - if not exist, create (support on-the-fly approach)
        - check whether a AnalysisRun record exists (it should if this is not the first/initial state)
            - if not exist, create
            - associate any libraries at this point (later updates/linking is not supported at this point)
        - check whether the state change event constitutes a new state
            - the DRAFT state allows payload updates, until it enters the READY state
            - the RUNNING state allows "infrequent" updates (i.e. that happen outside a certain time window)
            - other states will ignore updates of the same state
            - if we have new state, then persist it
            NOTE: all events that don't change any state value should be ignored
    """
    logger.info(f"Start processing {event}, {context}...")
    ari_object: ari.AnalysisRunInitiated = ari.AnalysisRunInitiated.model_validate_json(event)
    analysis: ari.Analysis = ari_object.analysis

    # We expect: a corresponding Analysis has to exist for each AnalysisRun
    try:
        logger.info(f"Looking for Analysis ({analysis.name}:{analysis.version}) with id {analysis.orcabusId}.")
        analysis_db: Analysis = Analysis.objects.get(
            orcabus_id=analysis.orcabusId
        )
    except Exception as e:
        logger.error("No Analysis record found!")
        raise e

    # then create the actual AnalysisRun entry
    # NOTE: since we process a request, we expect that the AnalysisRun does NOT exist yet
    ari_db: QuerySet = AnalysisRun.objects.query(analysis_run_name=ari_object.analysisRunName)
    if ari_db.exists():
        raise Exception("AnalysisRun record already exists!")
    else:
        logger.info("No AnalysisRun record found! Creating new entry.")

        analysis_run = AnalysisRun(
            analysis_run_name=ari_object.analysisRunName,
            status="DRAFT",
            analysis=analysis_db,
        )

        # attach the libraries associated with the AnalysisRunInitiated
        for ari_lib in ari_object.libraries:
            # get the DB record of the library
            try:
                db_lib: Library = Library.objects.get(orcabus_id=ari_lib.orcabusId)
            except Library.DoesNotExist:
                # The library record should exist - synced with metadata service on LibraryStateChange events
                # However, until that sync is in place we may need to create a record on demand
                # FIXME: remove this once library records are automatically synced
                db_lib = Library.objects.create(orcabus_id=ari_lib.orcabusId, library_id=ari_lib.libraryId)

            # add library to AnalysisRun object
            analysis_run.libraries.add(db_lib)

        logger.info(analysis_run)
        logger.info("Persisting AnalysisRun record.")
        analysis_run.save()

    logger.info(f"{__name__} done.")
    return analysis_run
