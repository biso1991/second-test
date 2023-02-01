from django.urls import path
from . import views
from rest_framework.routers import DefaultRouter

router_qa = DefaultRouter()
router_qa.register(r"projects", views.ProjectAPIView)
router_qa.register(r"files", views.FileAPIView)
router_qa.register(r"trainingjobs", views.TrainingJobAPIView)
router_qa.register(r"monitoring", views.TrainingMonitoringAPIView)
router_qa.register(r"models", views.ModelAPIView)
urlpatterns = [
    path(
        "qa_api/",
        views.GetQA_AnswersAPIView.as_view(),
        name="Get answers from question",
    ),
    path("vote/", views.VoteAPIView.as_view(), name="vote"),
    path(
        "training_action/",
        views.TrainingActionAPIView.as_view(),
        name="training_action",
    ),
    path(
        "verify_huggingface_url/",
        views.VerifyHuggingFaceUrlAPIView.as_view(),
        name="verify_huggingface_url",
    ),
    path(
        "startpreprocessing/",
        views.StartPreprocessingFiles.as_view(),
        name="start_preprocessing",
    ),
    path(
        "answer/",
        views.AnswersAPIView.as_view(),
        name="get_all_answers_list",
    ),
    path(
        "answer/<str:id>/",
        views.AnswersAPIView.as_view(),
        name="get_answer_by_id",
    ),
    path(
        "answer/<str:id>/<str:index>/",
        views.AnswersAPIView.as_view(),
        name="get_answer_by_id",
    ),
    path(
        "running_tasks/",
        views.RunningTasksAPIView.as_view(),
        name="get_Running_Tasks",
    ),
    path(
        "training_job_week/",
        views.TrainingJobStats.as_view(),
        name="get_training_job_stats_week",
    ),
]
