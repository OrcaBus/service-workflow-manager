from datetime import datetime, timedelta

from django.utils.timezone import make_aware

from workflow_manager.models import LibraryAssociation
from workflow_manager.tests.factories import PayloadFactory, LibraryFactory, WorkflowFactory, WorkflowRunFactory, \
    StateFactory


class TestData:
    """ImplNote: the class implemented fluent API. Chain each method calls to create the test fixture combo."""
    WORKFLOW_NAME = "TestWorkflow"
    STATUS_DRAFT = "DRAFT"
    STATUS_START = "READY"
    STATUS_RUNNING = "RUNNING"
    STATUS_END = "SUCCEEDED"
    STATUS_FAIL = "FAILED"
    STATUS_RESOLVED = "RESOLVED"

    def __init__(self):

        # Common components: payload and libraries
        self.generic_payload = PayloadFactory()  # Payload content is not important for now

        self.libraries = [
            LibraryFactory(orcabus_id="01J5M2JFE1JPYV62RYQEG99CP1", library_id="L000001"),
            LibraryFactory(orcabus_id="02J5M2JFE1JPYV62RYQEG99CP2", library_id="L000002"),
            LibraryFactory(orcabus_id="03J5M2JFE1JPYV62RYQEG99CP3", library_id="L000003"),
            LibraryFactory(orcabus_id="04J5M2JFE1JPYV62RYQEG99CP4", library_id="L000004")
        ]

    def create_primary(self):
        """
        Case: a primary workflow with two executions linked to 4 libraries
        The first execution failed and led to a repetition that succeeded
        """

        wf = WorkflowFactory(workflow_name=self.WORKFLOW_NAME + "Primary")

        # The first execution (workflow run 1)
        wfr_1 = WorkflowRunFactory(
            workflow_run_name=self.WORKFLOW_NAME + "PrimaryRun1",
            portal_run_id="1234",
            workflow=wf
        )

        for i, state in enumerate([self.STATUS_DRAFT, self.STATUS_START, self.STATUS_RUNNING, self.STATUS_FAIL]):
            StateFactory(workflow_run=wfr_1, status=state, payload=self.generic_payload,
                         timestamp=make_aware(datetime.now() + timedelta(hours=i)))
        for i in [0, 1, 2, 3]:
            LibraryAssociation.objects.create(
                workflow_run=wfr_1,
                library=self.libraries[i],
                association_date=make_aware(datetime.now()),
                status="ACTIVE",
            )

        # The second execution (workflow run 2)
        wfr_2 = WorkflowRunFactory(
            workflow_run_name=self.WORKFLOW_NAME + "PrimaryRun2",
            portal_run_id="1235",
            workflow=wf
        )
        for i, state in enumerate([self.STATUS_DRAFT, self.STATUS_START, self.STATUS_RUNNING, self.STATUS_END]):
            StateFactory(workflow_run=wfr_2, status=state, payload=self.generic_payload,
                         timestamp=make_aware(datetime.now() + timedelta(hours=i)))
        for i in [0, 1, 2, 3]:
            LibraryAssociation.objects.create(
                workflow_run=wfr_2,
                library=self.libraries[i],
                association_date=make_aware(datetime.now()),
                status="ACTIVE",
            )

        return self

    def create_secondary(self):
        """
        Case: a secondary pipeline comprising 3 workflows with corresponding executions
        First workflow: QC (2 runs for 2 libraries)
        Second workflow: Alignment (1 run for 2 libraries)
        Third workflow: VariantCalling (1 run for 2 libraries)
        """

        wf_qc = WorkflowFactory(workflow_name=self.WORKFLOW_NAME + "QC")

        # QC of Library 1
        wfr_qc_1 = WorkflowRunFactory(
            workflow_run_name=self.WORKFLOW_NAME + "QCRunLib1",
            portal_run_id="2345",
            workflow=wf_qc
        )
        for i, state in enumerate([self.STATUS_DRAFT, self.STATUS_START, self.STATUS_RUNNING, self.STATUS_END]):
            StateFactory(workflow_run=wfr_qc_1, status=state, payload=self.generic_payload,
                         timestamp=make_aware(datetime.now() + timedelta(hours=i)))
        LibraryAssociation.objects.create(
            workflow_run=wfr_qc_1,
            library=self.libraries[0],
            association_date=make_aware(datetime.now()),
            status="ACTIVE",
        )

        # QC of Library 2
        wfr_qc_2 = WorkflowRunFactory(
            workflow_run_name=self.WORKFLOW_NAME + "QCRunLib2",
            portal_run_id="2346",
            workflow=wf_qc
        )
        for i, state in enumerate(
                [self.STATUS_DRAFT, self.STATUS_START, self.STATUS_RUNNING, self.STATUS_FAIL, self.STATUS_RESOLVED]):
            StateFactory(workflow_run=wfr_qc_2, status=state, payload=self.generic_payload,
                         timestamp=make_aware(datetime.now() + timedelta(hours=i)))
        LibraryAssociation.objects.create(
            workflow_run=wfr_qc_2,
            library=self.libraries[1],
            association_date=make_aware(datetime.now()),
            status="ACTIVE",
        )

        # Alignment
        wf_align = WorkflowFactory(workflow_name=self.WORKFLOW_NAME + "Alignment")
        wfr_a = WorkflowRunFactory(
            workflow_run_name=self.WORKFLOW_NAME + "AlignmentRun",
            portal_run_id="3456",
            workflow=wf_align
        )
        for i, state in enumerate([self.STATUS_DRAFT, self.STATUS_START]):
            StateFactory(workflow_run=wfr_a, status=state, payload=self.generic_payload,
                         timestamp=make_aware(datetime.now() + timedelta(hours=i)))
        for i in [0, 1]:
            LibraryAssociation.objects.create(
                workflow_run=wfr_a,
                library=self.libraries[i],
                association_date=make_aware(datetime.now()),
                status="ACTIVE",
            )

        # Variant Calling
        wf_vc = WorkflowFactory(workflow_name=self.WORKFLOW_NAME + "VariantCalling")
        wfr_vc = WorkflowRunFactory(
            workflow_run_name=self.WORKFLOW_NAME + "VariantCallingRun",
            portal_run_id="4567",
            workflow=wf_vc
        )
        for i, state in enumerate([self.STATUS_DRAFT, self.STATUS_START, self.STATUS_RUNNING]):
            StateFactory(workflow_run=wfr_vc, status=state, payload=self.generic_payload,
                         timestamp=make_aware(datetime.now() + timedelta(hours=i)))
        for i in [0, 1]:
            LibraryAssociation.objects.create(
                workflow_run=wfr_vc,
                library=self.libraries[i],
                association_date=make_aware(datetime.now()),
                status="ACTIVE",
            )

        return self
