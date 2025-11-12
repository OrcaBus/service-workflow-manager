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
    states_transition_validation_map for state creation, update
    Structure:
    - If value is a list: ['STATE1', 'STATE2'] means only these states can transition to the key
    - If value is a dict with 'excluded_states': allows all states except those listed
    - If value is a dict with 'allowed_states': same as list format

    refer:
        "Resolved" -- https://github.com/umccr/orcabus/issues/593
        "Deprecated" -- https://github.com/umccr/orcabus/issues/695
    """
    states_transition_validation_map = {
        'RESOLVED': ['FAILED'],  # Only FAILED can transition to RESOLVED
        'DEPRECATED': {'excluded_states': ['FAILED', 'ABORTED', 'RESOLVED', 'DEPRECATED']}  # All states except these can transition to DEPRECATED
    }


    def get_queryset(self):
        return State.objects.filter(workflow_run=self.kwargs["orcabus_id"])

    @extend_schema(responses=OpenApiTypes.OBJECT, description="Get states transition validation map")
    @action(detail=False, methods=['get'], url_name='get_states_transition_validation_map', url_path='get_states_transition_validation_map')
    def get_states_transition_validation_map(self, request, **kwargs):
        """
        Returns states transition validation map.
        """
        return Response(self.states_transition_validation_map)

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

        # Check if the state being updated is in the validation map
        if instance.status not in self.states_transition_validation_map:
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

    def is_valid_next_state(self, current_status, request_status: str) -> bool:
        """
        Check if transitioning from current_status to request_status is valid.

        Uses states_transition_validation_map to determine validity:
        - If map entry is a list: only states in the list can transition
        - If map entry is a dict with 'excluded_states': all states except excluded ones can transition
        - If map entry is a dict with 'allowed_states': same as list format
        - If current_status is None (no state exists): only DEPRECATED is allowed
        """
        # Handle case when there's no current state - only allow DEPRECATED
        if current_status is None:
            return request_status.upper() == 'DEPRECATED'

        request_status_upper = request_status.upper()
        current_status_upper = current_status.upper()

        # Check if request_status is in the validation map
        if request_status_upper not in self.states_transition_validation_map:
            return False

        validation_rule = self.states_transition_validation_map[request_status_upper]

        # Handle dict format with 'excluded_states' or 'allowed_states'
        if isinstance(validation_rule, dict):
            if 'excluded_states' in validation_rule:
                # Allow all states except the excluded ones
                excluded_states = [s.upper() for s in validation_rule['excluded_states']]
                return current_status_upper not in excluded_states
            elif 'allowed_states' in validation_rule:
                # Only allow states in the allowed_states list
                allowed_states = [s.upper() for s in validation_rule['allowed_states']]
                return current_status_upper in allowed_states

        # Handle list format (backward compatibility and simpler format)
        if isinstance(validation_rule, list):
            allowed_states = [s.upper() for s in validation_rule]
            return current_status_upper in allowed_states

        return False
