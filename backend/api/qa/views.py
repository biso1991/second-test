from itertools import groupby
import json
from os.path import join
from django.conf import settings
from rest_framework.views import APIView
from api.qa.elasticsearchStore.elasticsearch import (
    Create_Elastic_Index_answers,
    insert_elastic_search_answers,
)
from api.qa.elasticsearchStore.services import (
    Delete_answers_from_elasticSearch,
    Get_answers_list_from_elasticSearch,
    Update_answers_from_elasticSearch,
    answers_to_elasticSearch,
)
from api.qa.haystack.haystack_train import Preprocessing_QA, training_job_loop
from rest_framework import status

from api.qa.pagination import CustomPageNumberPagination
from api.qa.redis.task_service import TaskService
from .utils import (
    Download_HuggingFace_Model,
    Extract_Compressed_File,
    get_hash,
    Format_average_documents,
    get_the_highest_depth,
    valid_filename,
    verifyHuggingFaceUrl,
)
from api.qa.models import Status, Training_Job_Monitoring
from .permissions import Has_permissionOrReadOnly
from .serializers import (
    AnswerSerialize,
    FileSerializeUpdate,
    ModelSerialize,
    MultiFileSerialize,
    QASerialize,
    TrainingActionsSerialize,
    TrainingJobSerialize,
    ProjectSerialize,
    FileSerialize,
    TrainingMonitoringSerialize,
)
from .models import Actions, Model, Project, File, Training_Job, scope, source
from rest_framework.response import Response
from rest_framework import viewsets, mixins
from api.qa import utils
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db.models import Q


class ProjectAPIView(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """This endpoint list,create,update and Destroy project from database"""

    queryset = Project.objects.all()
    serializer_class = ProjectSerialize
    pagination_class = CustomPageNumberPagination
    permission_classes = (Has_permissionOrReadOnly, IsAuthenticated)
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "model",
        "store_name",
    ]
    search_fields = ["name", "description"]
    ordering_fields = "__all__"

    # GET PROJECT BY OWNER
    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user.id)

    def create(self, request, *args, **kwargs):
        request.data["owner"] = request.user.id
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return super().create(request, *args, **kwargs)


class FileAPIView(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """This endpoint list,create,update and Destroy files from database"""

    queryset = File.objects.all()
    serializer_class = FileSerialize
    permission_classes = (Has_permissionOrReadOnly, IsAuthenticated)
    pagination_class = CustomPageNumberPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["project_f", "file_name", "extension"]
    search_fields = ["file_name"]
    ordering_fields = "__all__"

    # GET FIles BY Project Owner

    def get_queryset(self):
        projects_id = ()
        for project in Project.objects.all().filter(owner=self.request.user.id):
            projects_id = projects_id + (project.id,)
        return super().get_queryset().filter(project_f__in=projects_id)

    # Upload Many Files at once
    def create(self, request, *args, **kwargs):
        serializer = MultiFileSerialize(data=request.data)
        response = {}
        if serializer.is_valid():
            try:
                project = Project.objects.get(id=request.data.get("project_f"))
            except:
                return Response(
                    {"message": "No project found"}, status=status.HTTP_404_NOT_FOUND
                )
            if Has_permissionOrReadOnly.has_object_permission(
                self, request, None, project
            ):
                for file in serializer.validated_data["file_f"]:
                    exists_f = File.objects.filter(
                        file_name=valid_filename(file.name), project_f=project
                    )
                    if len(exists_f) == 0:
                        data = {
                            "file_f": file,
                            "project_f": serializer.validated_data["project_f"],
                        }
                        serializer_SingleFile = FileSerialize(data=data)
                        if serializer_SingleFile.is_valid():
                            serializer_SingleFile.save()
                            response[file.name] = {
                                "data": serializer_SingleFile.data,
                                "status": "success",
                            }
                        else:
                            response[file.name] = {
                                "data": serializer_SingleFile.errors,
                                "status": "error",
                            }
                return Response(response, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {"message": "You don't have permission to access this resource"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        serializer_SingleFileUpdate = FileSerializeUpdate(data=request.data)
        if serializer_SingleFileUpdate.is_valid():
            try:
                previous_f = File.objects.get(id=kwargs["pk"])
            except:
                return Response(
                    {"message": "No file found"}, status=status.HTTP_404_NOT_FOUND
                )
            try:
                project_n = Project.objects.get(
                    id=serializer_SingleFileUpdate.validated_data["project_f"]
                )
            except:
                return Response(
                    {"message": "No project found"}, status=status.HTTP_404_NOT_FOUND
                )
            if Has_permissionOrReadOnly.has_object_permission(
                self, request, None, previous_f.project_f
            ) and Has_permissionOrReadOnly.has_object_permission(
                self, request, None, project_n
            ):
                file_n = File()
                file_n.project_f = project_n
                file_n.file_f = previous_f.file_f
                data = {"file_f": file_n.file_f, "project_f": file_n.project_f.id}
                serializer_SingleFile2 = FileSerialize(data=data)
                # VERIFY THE EXISTANCE OF THE FILE
                if serializer_SingleFile2.is_valid():
                    file_search = File.objects.filter(
                        file_name=previous_f.file_name, project_f=file_n.project_f
                    )
                    if len(file_search) == 0:
                        try:
                            Delete_answers_from_elasticSearch(
                                previous_f.project_f.elastic_index_answers,
                                None,
                                previous_f.file_name,
                            )
                        except:
                            pass
                        file_n.file_f = None
                        file_n.file_f.save(
                            previous_f.file_name, previous_f.file_f, save=True
                        )
                        previous_f.delete()
                        file_n.save()
                        return Response({"id": file_n.id}, status=status.HTTP_200_OK)
                    else:
                        return Response(
                            {"message": "File already exists"},
                            status=status.HTTP_200_OK,
                        )
                else:
                    return Response(
                        serializer_SingleFile2.errors,
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {"message": "You don't have permission to access this resource"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            return Response(
                serializer_SingleFileUpdate.errors, status=status.HTTP_400_BAD_REQUEST
            )


class TrainingJobAPIView(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """This endpoint list,create,update and Destroy Training Job from database"""

    queryset = Training_Job.objects.all()
    serializer_class = TrainingJobSerialize
    permission_classes = (Has_permissionOrReadOnly, IsAuthenticated)
    pagination_class = CustomPageNumberPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["project", "status"]
    search_fields = ["name"]
    ordering_fields = "__all__"

    # GET Training Job BY Project Owner
    def get_queryset(self):
        projects_id = ()
        for project in Project.objects.all().filter(owner=self.request.user.id):
            projects_id = projects_id + (project.id,)
        return super().get_queryset().filter(project__in=projects_id)

    def create(self, request, *args, **kwargs):
        serializer = TrainingJobSerialize(data=request.data)
        if serializer.is_valid():
            try:
                ownerProject = Project.objects.get(
                    id=serializer.validated_data["project"].id
                )
            except:
                return Response(
                    {"message": "No project found"}, status=status.HTTP_404_NOT_FOUND
                )
            permission = Has_permissionOrReadOnly.has_object_permission(
                self, request, None, ownerProject
            )
            if permission == True:
                ownerProject.files_hash = get_hash(ownerProject)
                ownerProject.save()
                serializer.save()
                response = {"data": serializer.data, "status": "success"}
                return Response(response, status=status.HTTP_201_CREATED)
            else:
                response = {
                    "message": "You don't have permission to access this resource",
                    "status": "error",
                }
                return Response(response, status=status.HTTP_403_FORBIDDEN)
        else:
            response = {"message": serializer.errors, "status": "error"}
            return Response(response, status=status.HTTP_400_BAD_REQUEST)


class GetQA_AnswersAPIView(APIView):
    """This endpoint list all of the available QA Answers from Haystack"""

    # FIX QASerialize

    def post(self, request, *args, **kwargs):
        serializer = QASerialize(data=request.data)
        if serializer.is_valid():
            try:
                projectt = Project.objects.get(id=request.data.get("project"))
            except:
                return Response(
                    {"message": "No project found"}, status=status.HTTP_404_NOT_FOUND
                )
            permission = Has_permissionOrReadOnly.has_object_permission(
                self, request, None, projectt
            )
            if permission == True:
                query = request.data.get("query")
                result = Preprocessing_QA(projectt, False, query)
                result_dict = json.loads(result)
                result_dict["documents_average"] = Format_average_documents(
                    result_dict["documents"], projectt
                )
                response = {"data": result_dict, "status": "success"}
                return Response(response, status=status.HTTP_200_OK)
            else:
                response = {
                    "message": "You don't have permission to access this resource",
                    "status": "error",
                }
                return Response(response, status=status.HTTP_403_FORBIDDEN)
        else:
            response = {"message": serializer.errors, "status": "error"}
            return Response(response, status=status.HTTP_400_BAD_REQUEST)


class VoteAPIView(APIView):
    """This endpoint allows for voting on Answers"""

    def post(self, request, *args, **kwargs):
        serializer = AnswerSerialize(data=request.data)
        if serializer.is_valid():
            try:
                project = Project.objects.get(id=request.data.get("project"))
            except:
                return Response(
                    {"message": "No project found"}, status=status.HTTP_404_NOT_FOUND
                )
            permission = Has_permissionOrReadOnly.has_object_permission(
                self, request, None, project
            )
            if permission == True:
                project_answers_index = "{}-{}".format(
                    str(project.uuid), settings.ANSWERS_INDEX_NAME
                )
                elastic_search_data = answers_to_elasticSearch(request.data)
                Create_Elastic_Index_answers(project_answers_index)
                project.elastic_index_answers = project_answers_index
                insertion = insert_elastic_search_answers(
                    project_answers_index, elastic_search_data
                )
                project.vote = True
                project.save()
                if insertion == True:
                    response = {"status": "success"}
                    return Response(response, status=status.HTTP_200_OK)
                else:
                    response = {"status": "error"}
                    return Response(response, status=status.HTTP_400_BAD_REQUEST)
            else:
                response = {
                    "message": "You don't have permission to access this resource",
                    "status": "error",
                }
                return Response(response, status=status.HTTP_403_FORBIDDEN)
        else:
            response = {"message": serializer.errors, "status": "error"}
            return Response(response, status=status.HTTP_400_BAD_REQUEST)


class TrainingActionAPIView(APIView):
    """This endpoint allows for Starting , Pausing and Stopping a Training Job"""

    def post(self, request, *args, **kwargs):
        serializer = TrainingActionsSerialize(data=request.data)
        if serializer.is_valid():
            try:
                action = Actions(serializer.validated_data["action"])
            except:
                return Response(
                    {"message": "No action found"}, status=status.HTTP_400_BAD_REQUEST
                )
            try:
                training_job = Training_Job.objects.get(
                    id=serializer.validated_data["training_job"]
                )
            except:
                return Response(
                    {"message": "No Training Job found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            try:
                project = Project.objects.get(id=training_job.project.id)
            except:
                return Response(
                    {"message": "No Project found"}, status=status.HTTP_404_NOT_FOUND
                )
            if Has_permissionOrReadOnly.has_object_permission(
                self, request, None, project
            ):
                if (
                    training_job.status == Status.idle.value
                    or training_job.status == Status.aborted.value
                    or training_job.status == Status.failed.value
                    or training_job.status == Status.finished.value
                ) and action == Actions.start:
                    if project.vote != False:
                        try:
                            utils.answers_to_squad_format(project)
                        except:
                            return Response(
                                {"message": "Problem with Squad File"},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        training_job_loop_result = training_job_loop(training_job)
                        if training_job_loop_result["result"] == True:
                            response = {
                                "celery_id": training_job_loop_result["id"],
                                "status": "success",
                            }
                            return Response(response, status=status.HTTP_200_OK)
                        else:
                            response = {"status": "error"}
                            return Response(
                                response, status=status.HTTP_400_BAD_REQUEST
                            )
                    else:
                        return Response(
                            {"status": "error"}, status=status.HTTP_400_BAD_REQUEST
                        )
                elif (
                    training_job.status == Status.running.value
                    and action == Actions.stop
                ):
                    # celery_app.control.time_limit("api.celery.async_task.Training_Loop_Async", soft=1, hard=1, reply=True)
                    # celery_app.control.terminate(training_job.celery_task_id, signal='SIGKILL')
                    cache.set(training_job.celery_task_id, "stop")
                    return Response({"status": "success"}, status=status.HTTP_200_OK)
                elif (
                    training_job.status == Status.running.value
                    and action == Actions.start
                ):
                    return Response(
                        {"message": "Training Job is already running"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                elif (
                    training_job.status == Status.finished.value
                    or training_job.status == Status.aborted.value
                    or training_job.status == Status.idle.value
                ) and action == Actions.stop:
                    return Response(
                        {"message": "Training Job is already stopped"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                else:
                    return Response(
                        {"message": "ERROR"}, status=status.HTTP_405_METHOD_NOT_ALLOWED
                    )
            else:
                response = {
                    "message": "You don't have permission to access this resource",
                    "status": "error",
                }
                return Response(response, status=status.HTTP_403_FORBIDDEN)
        else:
            response = {"message": serializer.errors, "status": "error"}
            return Response(response, status=status.HTTP_400_BAD_REQUEST)


class TrainingMonitoringAPIView(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """This endpoint list and retrieve Training Monitoring from database"""

    queryset = Training_Job_Monitoring.objects.all()
    serializer_class = TrainingMonitoringSerialize
    permission_classes = (Has_permissionOrReadOnly, IsAuthenticated)
    pagination_class = CustomPageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["training_job"]
    ordering_fields = "__all__"


class ModelAPIView(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """This endpoint list,create,update and Destroy Model from database"""

    queryset = Model.objects.all()
    serializer_class = ModelSerialize
    permission_classes = (IsAuthenticated,)
    pagination_class = CustomPageNumberPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["scope", "source"]
    search_fields = ["model_name", "model_ref_url", "scope", "source"]
    ordering_fields = "__all__"

    # GET MODELS BY OWNER and Public scope
    def get_queryset(self):
        # Using Django queue to get the public and the owned models
        scope_condition = Q(scope=scope.PUBLIC.value)
        owner_condition = Q(owner=self.request.user.id)
        return super().get_queryset().filter(scope_condition | owner_condition)

    def create(self, request, *args, **kwargs):
        serializer = ModelSerialize(data=request.data)
        if serializer.is_valid():
            model_ref_url = serializer.validated_data.get("model_ref_url")
            model_file = serializer.validated_data.get("model_file")
            # Check if the user inserted a HuggingFace Model Url
            if model_ref_url is not None:
                result = Download_HuggingFace_Model(model_ref_url)
                # Check if the model is already exists in the models dir and database
                if result["local"] == True:
                    response = {
                        "message": "Model already exists",
                        "data": Model.objects.get(model_ref_url=model_ref_url).id,
                        "status": "success",
                    }
                    return Response(response, status=status.HTTP_200_OK)
                else:
                    serializer.validated_data["model_ref_path"] = result["path"]
                    serializer.validated_data["uuid"] = result["uuid"]
                    serializer.validated_data["source"] = source.AUTOMATIC.value
                    serializer.save()
                    response = {
                        "message": "Model created successfully",
                        "data": serializer.data,
                        "status": "success",
                    }
                    return Response(response, status=status.HTTP_201_CREATED)
            # Check if the user uploaded a model file
            elif model_file is not None:
                # serializer.save() to save the model file and the model
                serializer.validated_data["source"] = source.MANUAL.value
                model_saved = serializer.save()
                model_saved.model_ref_path = get_the_highest_depth(
                    Extract_Compressed_File(
                        model_saved,
                        join(settings.MEDIA_ROOT, str(model_saved.model_file)),
                    )
                )
                model_saved.save()
                response = {
                    "message": "Model created successfully",
                    "data": serializer.data,
                    "status": "success",
                }
                return Response(response, status=status.HTTP_201_CREATED)
        else:
            response = {"message": serializer.errors, "status": "error"}
            return Response(response, status=status.HTTP_400_BAD_REQUEST)


class VerifyHuggingFaceUrlAPIView(APIView):
    """This endpoint verify if the model url is a valid hugging face model url"""

    def post(self, request, *args, **kwargs):
        if request.data.get("url"):
            url = request.data.get("url")
            result = verifyHuggingFaceUrl(url)
            if result == True:
                response = {"message": True, "status": "success"}
                return Response(response, status=status.HTTP_200_OK)
            else:
                response = {"message": False, "status": "error"}
                return Response(response, status=status.HTTP_200_OK)
        else:
            response = {"message": "No URL provided", "status": "error"}
            return Response(response, status=status.HTTP_400_BAD_REQUEST)


class StartPreprocessingFiles(APIView):
    """This endpoint start the preprocessing of the files"""

    def post(self, request, *args, **kwargs):
        if request.data.get("project"):
            result = None
            project_id = request.data.get("project")
            project = Project.objects.get(id=project_id)
            if project.owner == request.user:
                if utils.is_files_changed(project) == True:
                    project.files_ready = False
                    project.save()
                    result = Preprocessing_QA(project, True)
                if result == True:
                    response = {"message": True, "status": "success"}
                    return Response(response, status=status.HTTP_200_OK)
                else:
                    response = {"message": False, "status": "error"}
                    return Response(response, status=status.HTTP_200_OK)
            else:
                response = {
                    "message": "You don't have permission to access this resource",
                    "status": "error",
                }
                return Response(response, status=status.HTTP_403_FORBIDDEN)
        else:
            response = {"message": "No Project ID provided", "status": "error"}
            return Response(response, status=status.HTTP_400_BAD_REQUEST)


class AnswersAPIView(
    APIView, CustomPageNumberPagination, filters.OrderingFilter, filters.SearchFilter
):
    """This endpoint list,create,update and Destroy Answers from ElasticSearch"""

    serializer_class = None
    ordering_fields = ["score", "project_id", "answer", "Date", "chosen"]
    search_fields = ["answer", "query"]

    def get(self, request, **kwargs):
        answerId = kwargs.get("id")
        project_id = self.request.query_params.get("project_id")
        answers = []
        indices_list = []
        indices_list_by_project = {}
        projects = Project.objects.filter(owner=request.user.id)
        if len(projects) != 0:
            for project in projects:
                if project.vote == True and project.elastic_index_answers is not None:
                    indices_list.append(project.elastic_index_answers)
                    indices_list_by_project[project.elastic_index_answers] = {
                        "id": project.id,
                        "name": project.name,
                    }
            if len(indices_list) != 0:
                answers = Get_answers_list_from_elasticSearch(indices_list, 1)
            for answer in answers:
                answer["project_id"] = indices_list_by_project[answer["index"]]["id"]
                answer["project_name"] = indices_list_by_project[answer["index"]][
                    "name"
                ]
        if project_id is not None:
            answers = [
                answer for answer in answers if answer["project_id"] == int(project_id)
            ]
        if answerId is not None:
            answers = [answer for answer in answers if answer["id"] == answerId]
        ordering = self.get_ordering(request, answers, view=self)
        if ordering != None and len(ordering) == 1:
            if ordering[0].startswith("-") == True:
                ordering_String = ordering[0][1:]
                answers = sorted(
                    answers, key=lambda k: k[str(ordering_String)], reverse=True
                )
            else:
                answers = sorted(answers, key=lambda k: k[str(ordering[0])])
        search = self.get_search_terms(request)
        if search != None and len(search) == 1:
            new_answers = []
            for answer in answers:
                if (
                    answer["answer"].find(search[0]) != -1
                    or answer["query"].find(search[0]) != -1
                ):
                    new_answers.append(answer)
            answers = new_answers
        results = self.paginate_queryset(answers, request, view=self)
        return self.get_paginated_response(results)

    def delete(self, request, **kwargs):
        answerId = kwargs.get("id")
        index = kwargs.get("index")
        if answerId is not None and index is not None:
            project = Project.objects.get(elastic_index_answers=index)
            listId = []
            listId.append(str(answerId))
            if project.owner == request.user:
                result = Delete_answers_from_elasticSearch(index, listId)
                if result == True:
                    response = {
                        "message": "Answer deleted successfully",
                        "status": "success",
                    }
                    return Response(response, status=status.HTTP_204_NO_CONTENT)
                else:
                    response = {"message": "Answer not deleted", "status": "error"}
                    return Response(response, status=status.HTTP_400_BAD_REQUEST)
            else:
                response = {
                    "message": "You don't have permission to access this resource",
                    "status": "error",
                }
                return Response(response, status=status.HTTP_403_FORBIDDEN)
        else:
            response = {"message": "No Answer ID or Index provided", "status": "error"}
            return Response(response, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, **kwargs):
        answerId = kwargs.get("id")
        index = kwargs.get("index")
        chosen = request.data.get("chosen")
        if answerId is not None and index is not None:
            if chosen is not None:
                project = Project.objects.get(elastic_index_answers=index)
                if project.owner == request.user:
                    result = Update_answers_from_elasticSearch(index, answerId, chosen)
                    if result == True:
                        response = {
                            "message": "Answer updated successfully",
                            "status": "success",
                        }
                        return Response(response, status=status.HTTP_200_OK)
                    else:
                        response = {"message": "Answer not updated", "status": "error"}
                        return Response(response, status=status.HTTP_400_BAD_REQUEST)
                else:
                    response = {
                        "message": "You don't have permission to access this resource",
                        "status": "error",
                    }
                    return Response(response, status=status.HTTP_403_FORBIDDEN)
            else:
                response = {"message": "No chosen value provided", "status": "error"}
                return Response(response, status=status.HTTP_400_BAD_REQUEST)
        else:
            response = {"message": "No Answer ID or Index provided", "status": "error"}
            return Response(response, status=status.HTTP_400_BAD_REQUEST)


class RunningTasksAPIView(APIView):
    """This endpoint list RunningTasks from Redis"""

    def get(self, request, **kwargs):
        user_id = request.user.id
        redis_task = TaskService(user_id)
        running_tasks = redis_task.getRunningTasks()
        return Response(running_tasks, status=status.HTTP_200_OK)


class TrainingJobStats(APIView):
    """This endpoint list TrainingJobStats"""

    def get(self, request, **kwargs):
        user_id = request.user.id
        listTrainingJob = []
        projects = Project.objects.filter(owner=user_id)
        if len(projects) != 0:
            for project in projects:
                trainingJob = Training_Job.objects.filter(project=project.id)
                if len(trainingJob) != 0:
                    for job in trainingJob:
                        listTrainingJob.append(job)
            if len(listTrainingJob) != 0:
                # group by create_date and count the number of jobs per day
                listTrainingJob = sorted(listTrainingJob, key=lambda k: k.create_date)
                listTrainingJob = groupby(
                    listTrainingJob, lambda x: x.create_date.date()
                )
                listTrainingJob = [
                    (key, len(list(group))) for key, group in listTrainingJob
                ]
                listTrainingJob = listTrainingJob[-7:]
                return Response(listTrainingJob, status=status.HTTP_200_OK)
            else:
                return Response(listTrainingJob, status=status.HTTP_200_OK)
        else:
            return Response(listTrainingJob, status=status.HTTP_200_OK)
