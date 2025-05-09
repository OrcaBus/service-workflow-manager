from django.db.models import Q, Max, F
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action

from workflow_manager.models.workflow_run import WorkflowRun
from workflow_manager.serializers.workflow_run import WorkflowRunListParamSerializer, WorkflowRunDetailSerializer, WorkflowRunSerializer
from workflow_manager.viewsets.base import BaseViewSet


class WorkflowRunViewSet(BaseViewSet):
    serializer_class = WorkflowRunDetailSerializer
    search_fields = WorkflowRun.get_base_fields()
    queryset = WorkflowRun.objects.prefetch_related("libraries").all()
    termination_statuses = ["FAILED", "ABORTED", "SUCCEEDED", "RESOLVED", "DEPRECATED"]

    @extend_schema(parameters=[WorkflowRunListParamSerializer])
    def list(self, request, *args, **kwargs):
        self.serializer_class = WorkflowRunSerializer  # use simple view for record listing
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        """
        custom queryset:
        add filter by:
        start_time, end_time : range of latest state timestamp
        is_ongoing : filter by ongoing workflow runs
        status : filter by latest state status

        add search terms:
        library_id: filter by library_id
        orcabus_id: filter by orcabus_id
        """
        # default time is 0
        start_time = self.request.query_params.get('start_time', 0)
        end_time = self.request.query_params.get('end_time', 0)

        # get is ongoing flag
        is_ongoing = self.request.query_params.get('is_ongoing', 'false')

        # get status
        status = self.request.query_params.get('status', '')

        # get search query params
        search_params = self.request.query_params.get('search', '')

        # exclude the custom query params from the rest of the query params
        def exclude_params(params):
            for param in params:
                self.request.query_params.pop(param) if param in self.request.query_params.keys() else None

        exclude_params([
            'start_time',
            'end_time',
            'is_ongoing',
            'status',
            'search'
        ])

        # get all workflow runs with rest of the query params
        # add prefetch_related & select_related to reduce the number of queries
        result_set = WorkflowRun.objects.get_by_keyword(**self.request.query_params).distinct()\
                                        .prefetch_related('states')\
                                        .prefetch_related('libraries')\
                                        .select_related('workflow')

        if start_time and end_time:
            result_set = result_set.annotate(latest_state_time=Max('states__timestamp')).filter(
                latest_state_time__range=[start_time, end_time]
            )

        if is_ongoing.lower() == 'true':
            result_set = result_set.filter(
                ~Q(states__status__in=self.termination_statuses)
            )

        if status:
            result_set = result_set.annotate(latest_state_time=Max('states__timestamp')).filter(
                states__timestamp=F('latest_state_time'),
                states__status=status.upper()
            )

        # Combine search across multiple fields (worfkflow run name, comment, library_id, orcabus_id, workflow name)
        if search_params:
            result_set = result_set.filter(
                Q(workflow_run_name__icontains=search_params) |
                Q(comment__icontains=search_params) |
                Q(libraries__library_id__icontains=search_params) |
                Q(libraries__orcabus_id__icontains=search_params) |
                Q(workflow__workflow_name__icontains=search_params)
            ).distinct() # Add distinct to remove duplicates

        return result_set

    @action(detail=False, methods=['GET'])
    def ongoing(self, request):
        self.serializer_class = WorkflowRunSerializer  # use simple view for record listing
        # Get all books marked as favorite
        ordering = self.request.query_params.get('ordering', '-orcabus_id')

        if "status" in self.request.query_params.keys():
            status = self.request.query_params.get('status')
            result_set = WorkflowRun.objects.get_by_keyword(states__status=status).order_by(ordering)
        else:
            result_set = WorkflowRun.objects.get_by_keyword(**self.request.query_params).order_by(ordering)

        result_set = result_set.filter(
            ~Q(states__status__in=self.termination_statuses)
        )
        pagw_qs = self.paginate_queryset(result_set)
        serializer = self.get_serializer(pagw_qs, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['GET'])
    def unresolved(self, request):
        self.serializer_class = WorkflowRunSerializer  # use simple view for record listing
        # Get all books marked as favorite
        ordering = self.request.query_params.get('ordering', '-orcabus_id')

        result_set = WorkflowRun.objects.get_by_keyword(states__status="FAILED").order_by(ordering)

        result_set = result_set.filter(
            ~Q(states__status="RESOLVED")
        )
        pagw_qs = self.paginate_queryset(result_set)
        serializer = self.get_serializer(pagw_qs, many=True)
        return self.get_paginated_response(serializer.data)
