from rest_framework import serializers


from api.qa.elasticsearchStore.services import Get_Answer_Count_By_Chosen


from .models import Model, Project, File, Status, Training_Job, Training_Job_Monitoring


class ProjectSerialize(serializers.ModelSerializer):
    # Number of trainingJob by project
    training_job_status_project = serializers.SerializerMethodField()
    latest_training = serializers.SerializerMethodField()
    model_name = serializers.SerializerMethodField()
    nb_files = serializers.SerializerMethodField()
    nb_Answers = serializers.SerializerMethodField()

    def get_nb_Answers(self, obj):
        return Get_Answer_Count_By_Chosen(obj.elastic_index_answers)

    def get_nb_files(self, obj):
        return len(File.objects.filter(project_f=obj.id))

    def get_training_job_status_project(self, obj):
        status = {"running": False, "finished": False}
        if (
            len(
                Training_Job.objects.filter(status=Status.running.value, project=obj.id)
            )
            > 0
        ):
            status["running"] = True
        if (
            len(
                Training_Job.objects.filter(
                    status=Status.finished.value, project=obj.id
                )
            )
            > 0
        ):
            status["finished"] = True
        return status

    def get_latest_training(self, obj):
        latest_training = Training_Job.objects.filter(project=obj.id).order_by("-id")
        if len(latest_training) > 0:
            return latest_training[0].update_date
        else:
            return "none"

    def get_model_name(self, obj):
        model_name = Model.objects.filter(id=obj.model.id)
        if len(model_name) > 0:
            return model_name[0].model_name
        else:
            return "none"

    class Meta:
        model = Project
        fields = "__all__"  # get all the field in the class


class GetProjectByUserSerialize(serializers.Serializer):

    owner = serializers.CharField(required=True)


class ModelSerialize(serializers.ModelSerializer):
    class Meta:
        model = Model
        fields = "__all__"  # get all the field in the class


class FileSerialize(serializers.ModelSerializer):
    Project_name = serializers.SerializerMethodField()

    def get_Project_name(self, obj):
        project_name = Project.objects.filter(id=obj.project_f.id)
        return project_name[0].name

    class Meta:
        model = File
        fields = "__all__"  # get all the field in the class


class MultiFileSerialize(serializers.Serializer):
    file_f = serializers.ListField(child=serializers.FileField(required=True))
    project_f = serializers.IntegerField(required=True)


class FileSerializeUpdate(serializers.Serializer):
    project_f = serializers.IntegerField(required=True)


class TrainingJobSerialize(serializers.ModelSerializer):
    Project_name = serializers.SerializerMethodField()

    def get_Project_name(self, obj):
        project_name = Project.objects.filter(id=obj.project.id)
        return project_name[0].name

    class Meta:
        model = Training_Job
        fields = "__all__"


class QASerialize(serializers.Serializer):
    """
    Serializer for QA
    """

    project = serializers.IntegerField(required=True)
    query = serializers.CharField(required=True)


class SingleAnswerSerialize(serializers.Serializer):
    """
    Serializer for QA
    """

    context = serializers.CharField(required=True)
    answer = serializers.CharField(required=True)
    offsets_in_context = serializers.ListField(required=True)
    chosen = serializers.BooleanField(required=True)


class SingleDocumentSerialize(serializers.Serializer):
    """
    Serializer for Document
    """

    name = serializers.CharField(required=True)
    score = serializers.FloatField(required=True)


class AnswerSerialize(serializers.Serializer):
    """
    Serializer for Vote Answers
    """

    project = serializers.IntegerField(required=True)
    query = serializers.CharField(required=True)
    answers = serializers.ListField(child=SingleAnswerSerialize(), required=True)
    documents = serializers.ListField(child=SingleDocumentSerialize(), required=True)


class TrainingActionsSerialize(serializers.Serializer):
    """
    Serializer for Training Actions
    """

    training_job = serializers.IntegerField(required=True)
    action = serializers.IntegerField(required=True)


class TrainingMonitoringSerialize(serializers.ModelSerializer):
    """
    Serializer for Training Monitoring
    """

    training_job_id = serializers.SerializerMethodField()
    training_job_name = serializers.SerializerMethodField()

    def get_training_job_id(self, obj):
        return obj.training_job.id

    def get_training_job_name(self, obj):
        return obj.training_job.name

    class Meta:
        model = Training_Job_Monitoring
        fields = "__all__"
