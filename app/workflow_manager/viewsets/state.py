from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, PolymorphicProxySerializer
from rest_framework.decorators import action
from rest_framework import mixins, status
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from django.utils import timezone

from workflow_manager.models import State, WorkflowRun
from workflow_manager.serializers.state import StateSerializer


class StateViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.ListModelMixin,  GenericViewSet):
    serializer_class = StateSerializer
    search_fields = State.get_base_fields()
    http_method_names = ['get', 'post', 'patch']
    pagination_class = None
    lookup_value_regex = "[^/]+" # to allow id prefix

    """
    valid_states_map for state creation, update
    refer:
        "Resolved" -- https://github.com/umccr/orcabus/issues/593
        "Deprecated" -- https://github.com/umccr/orcabus/issues/695
    """
    # valid states map for state creation, update
    valid_states_map = {
        'RESOLVED': ['FAILED'],
        'DEPRECATED': []  # Handled specially - allows all states except those in excluded_states_map
    }

    # States that are excluded from certain transitions
    # For DEPRECATED: all states except these can be deprecated
    excluded_states_map = {
        'DEPRECATED': ['FAILED', 'ABORTED', 'RESOLVED', 'DEPRECATED']
    }

    def get_queryset(self):
        return State.objects.filter(workflow_run=self.kwargs["orcabus_id"])

    @extend_schema(responses=OpenApiTypes.OBJECT, description="Get valid next states for the current workflow run based on its latest state")
    @action(detail=False, methods=['get'], url_name='valid_next_states', url_path='valid_next_states')
    def get_valid_next_states(self, request, **kwargs):
        """
        Returns valid next states based on the workflow run's latest state.
        Similar to create() function - gets the latest state and determines what states can be added.
        """
        wfr_orcabus_id = self.kwargs.get("orcabus_id")
        try:
            workflow_run = WorkflowRun.objects.get(orcabus_id=wfr_orcabus_id)
        except WorkflowRun.DoesNotExist:
            return Response({"detail": "Workflow run '{}' not found".format(wfr_orcabus_id)},
                          status=status.HTTP_404_NOT_FOUND)

        latest_state = workflow_run.get_latest_state()
        if not latest_state:
            # When there's no state, allow DEPRECATED (since it's not in excluded states)
            return Response({
                "current_state": None,
                "valid_next_states": ["DEPRECATED"],
                "detail": "No state found for workflow run '{}'. DEPRECATED is allowed.".format(wfr_orcabus_id)
            })

        current_status = latest_state.status
        valid_next_states = self.get_valid_next_states(current_status)

        return Response({
            "current_state": current_status,
            "valid_next_states": valid_next_states
        })

    def create(self, request, *args, **kwargs):
        """
        Create a customed new state for a workflow run.
        Currently we support "Resolved", "Deprecated"
        """
        wfr_orcabus_id = self.kwargs.get("orcabus_id")
        workflow_run = WorkflowRun.objects.get(orcabus_id=wfr_orcabus_id)

        latest_state = workflow_run.get_latest_state()
        request_status = request.data.get('status', '').upper()

        # Handle case when there's no latest state - only allow DEPRECATED
        if not latest_state:
            if request_status != 'DEPRECATED':
                return Response({"detail": "No state found for workflow run '{}'. Only DEPRECATED is allowed when there are no states.".format(wfr_orcabus_id)},
                                status=status.HTTP_400_BAD_REQUEST)
            # Allow DEPRECATED when there's no state (it's not in excluded states)
            latest_status = None
        else:
            latest_status = latest_state.status
            # check if the state status is valid
            if not self.is_valid_next_state(latest_status, request_status):
                return Response({"detail": "Invalid state request. Can't add state '{}' to '{}'".format(request_status, latest_status)},
                                status=status.HTTP_400_BAD_REQUEST)

        # comment is required when request change state
        if not request.data.get('comment'):
            return Response({"detail": "Comment is required when request status is '{}'".format(request_status)},
                            status=status.HTTP_400_BAD_REQUEST)

        # Prepare data for serializer
        data = request.data.copy()
        data['timestamp'] = timezone.now()
        data['workflow_run'] = wfr_orcabus_id
        data['status'] = request_status

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        # Check if the state being updated is "Resolved"
        if instance.status not in self.valid_states_map:
            return Response({"detail": "Invalid state status."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Check if only the comment field is being updated
        if set(request.data.keys()) != {'comment'}:
            return Response({"detail": "Only the comment field can be updated."},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)


    def get_valid_next_states(self, current_status):
        """
        Get all valid next states for a given current state.
        Returns a list of state names that can be transitioned to from the current state.
        If current_status is None (no state exists), returns ['DEPRECATED'].
        """
        # Handle case when there's no current state
        if current_status is None:
            return ['DEPRECATED']

        valid_states = set()
        current_status_upper = current_status.upper()

        # Check each possible target state in valid_states_map
        for target_state in self.valid_states_map.keys():
            if self.is_valid_next_state(current_status_upper, target_state):
                valid_states.add(target_state)
        for target_state in self.excluded_states_map.keys():
            if self.is_valid_next_state(current_status_upper, target_state):
                valid_states.add(target_state)
        return list(valid_states)

    def is_valid_next_state(self, current_status: str, request_status: str) -> bool:
        """
        check if the state status is valid:
        valid_states_map[request_state] == current_state.status
        excluded_states_map[request_state] == current_state.status
        if valid_states_map[request_state] is empty, allow all states except the excluded ones
        if excluded_states_map[request_state] is empty, allow all states except the valid ones
        """
        current_status_upper = current_status.upper()
        request_status_upper = request_status.upper()

        # Special handling: if valid_states_map entry is empty, check excluded_states_map
        # This allows all states except the excluded ones
        if not self.valid_states_map[request_status_upper]:
            if request_status_upper in self.excluded_states_map:
                excluded_states = [s.upper() for s in self.excluded_states_map[request_status_upper]]
                return current_status_upper not in excluded_states  # allow all states except the excluded ones
        return current_status_upper in self.valid_states_map[request_status_upper]  # check against the valid_states_map
