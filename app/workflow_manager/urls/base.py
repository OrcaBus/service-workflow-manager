from django.urls import path, include
from django.urls import path
from drf_spectacular.views import SpectacularJSONAPIView, SpectacularSwaggerView

from workflow_manager.routers import OptionalSlashDefaultRouter
from workflow_manager.viewsets.analysis import AnalysisViewSet
from workflow_manager.viewsets.analysis_run import AnalysisRunViewSet
from workflow_manager.viewsets.workflow import WorkflowViewSet
from workflow_manager.viewsets.workflow_run import WorkflowRunViewSet
from workflow_manager.viewsets.payload import PayloadViewSet
from workflow_manager.viewsets.analysis_context import AnalysisContextViewSet
from workflow_manager.viewsets.state import StateViewSet
from workflow_manager.viewsets.workflow_run_action import WorkflowRunActionViewSet
# from workflow_manager.viewsets.library import LibraryViewSet
from workflow_manager.viewsets.workflow_run_comment import WorkflowRunCommentViewSet
from workflow_manager.viewsets.workflow_run_stats import WorkflowRunStatsViewSet
from workflow_manager.settings.base import API_VERSION

api_namespace = "api"
api_version = API_VERSION
api_base = f"{api_namespace}/{api_version}/"

router = OptionalSlashDefaultRouter()

router.register(r"workflowrun/stats", WorkflowRunStatsViewSet, basename="workflowrun_stats")
router.register(r"analysis", AnalysisViewSet, basename="analysis")
router.register(r"analysisrun", AnalysisRunViewSet, basename="analysisrun")
router.register(r"analysiscontext", AnalysisContextViewSet, basename="analysiscontext")
router.register(r"workflow", WorkflowViewSet, basename="workflow")
router.register(r"workflowrun", WorkflowRunViewSet, basename="workflowrun")
router.register(r"workflowrun", WorkflowRunActionViewSet, basename="workflowrun-action")
router.register(r"payload", PayloadViewSet, basename="payload")

router.register(
    "workflowrun/(?P<orcabus_id>[^/]+)/state",
    StateViewSet,
    basename="workflowrun-state",
)

# router.register(
#     "workflowrun/(?P<workflowrun_id>[^/]+)/library",
#     LibraryViewSet,
#     basename="workflowrun-library",
# )

router.register(
    "workflowrun/(?P<orcabus_id>[^/]+)/comment",
    WorkflowRunCommentViewSet,
    basename="workflowrun-comment",
)

urlpatterns = [
    path(f"{api_base}", include(router.urls)),
    path('schema/openapi.json', SpectacularJSONAPIView.as_view(), name='schema'),
    path('schema/swagger-ui/',
         SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

handler500 = "rest_framework.exceptions.server_error"
handler400 = "rest_framework.exceptions.bad_request"
