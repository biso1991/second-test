import os
import enum
from django.conf import settings
from django.db import models
from api.qa.elasticsearchStore.services import Delete_answers_from_elasticSearch
from api.users.models import User
import uuid
from django.core.validators import FileExtensionValidator
from django.db.models.signals import post_save
from django.dispatch import receiver

# flake8: noqa F401
from .validators import file_size


def upload_model_path_handler(instance, filename):
    return "{models}/{uuid}/{fname}".format(
        models=settings.ROOT_MODELS_DIR, uuid=instance.uuid, fname=filename
    )


# Extract the model from the zip file Uploaded by the user
def Extract_Compressed_File(model, model_ref_path):
    from zipfile import ZipFile
    import rarfile

    if model.model_file:
        fn, ext = os.path.splitext(model.model_file.name)
        extension = ext[1:]
        model_dir = os.path.dirname(model_ref_path)
        if extension == "zip":
            with ZipFile(model_ref_path, "r") as zipObj:
                zipObj.extractall(model_dir)
                zipObj.close()
                from haystack.nodes import FARMReader

                reader = FARMReader(
                    model_name_or_path=get_the_highest_depth(model_dir),
                    use_gpu=True,
                    progress_bar=True,
                    force_download=False,
                )
                reader.save(directory=get_the_highest_depth(model_dir))
                return model_dir
        elif extension == "rar":
            rar = rarfile.RarFile(model_ref_path)
            rar.extractall(model_dir)
            rar.close()
            from haystack.nodes import FARMReader

            reader = FARMReader(
                model_name_or_path=get_the_highest_depth(model_dir),
                use_gpu=True,
                progress_bar=True,
                force_download=False,
            )
            reader.save(directory=get_the_highest_depth(model_dir))
            return model_dir


def get_the_highest_depth(path):
    from os import listdir
    from os.path import isdir, join

    exists = False
    dir = ""
    # loop through all the files in the directory
    for f in listdir(path):
        if f == "tokenizer.json":
            exists = True
        elif isdir(join(path, f)):
            dir = f
    if exists == True:
        return path
    else:
        return get_the_highest_depth(path + "/" + dir + "/")


class scope(enum.Enum):
    PRIVATE = 0
    PUBLIC = 1
    scope_choices = (
        (PRIVATE, "Private"),
        (PUBLIC, "Public"),
    )


class source(enum.Enum):
    MANUAL = 0
    AUTOMATIC = 1
    sources_choices = (
        (MANUAL, "MANUAL"),
        (AUTOMATIC, "AUTOMATIC"),
    )


class Model(models.Model):
    # ADD CREATION AND UPDATING DATE
    model_name = models.CharField("model_name", max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    model_ref_url = models.CharField(
        "model_ref_url", max_length=244, default="", blank=True
    )
    model_ref_path = models.CharField(
        "model_ref_path", max_length=244, default="", blank=True
    )
    scope = models.IntegerField(
        "scope", choices=scope.scope_choices.value, default=scope.PRIVATE.value
    )
    source = models.IntegerField(
        "source", choices=source.sources_choices.value, default=source.AUTOMATIC.value
    )
    uuid = models.UUIDField("uuid", default=uuid.uuid4, editable=True)
    model_file = models.FileField(
        null=True,
        upload_to=upload_model_path_handler,
        blank=True,
        validators=[FileExtensionValidator(["rar", "zip"])],
    )
    create_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "model_db"

    def save(self, *args, **kwargs):
        if self.owner.is_superuser:
            if self.model_ref_url != "":
                from haystack.nodes import FARMReader

                uuid_model = uuid.uuid4().hex
                directory = "{}/{}".format(settings.ROOT_MODELS_DIR, uuid_model)
                reader = FARMReader(
                    model_name_or_path=self.model_ref_url,
                    use_gpu=True,
                    progress_bar=True,
                    force_download=False,
                )
                reader.save(directory=directory)
        super().save(*args, **kwargs)


@receiver(post_save, sender=Model)
def extract_model_from_zip(sender, instance, **kwargs):
    if (
        instance.model_file is not None
        and instance.model_ref_path == ""
        and instance.owner.is_superuser
    ):
        from os.path import join

        instance.model_ref_path = get_the_highest_depth(
            Extract_Compressed_File(
                instance, join(settings.MEDIA_ROOT, str(instance.model_file))
            )
        )
        instance.source = source.MANUAL.value
        instance.save()
    else:
        pass


class Project(models.Model):
    splitting = (("word", 0), ("sentence", 1), ("passage", 2))
    preprocessing_optionss = (("sliding-window", 0), ("simple-text-splitting", 1))
    name = models.CharField("name", max_length=255)
    description = models.TextField("description", max_length=300)
    owner = models.ForeignKey(User, on_delete=models.deletion.CASCADE, null=True)
    uuid = models.UUIDField("uuid", default=uuid.uuid4, editable=False)
    create_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)
    model = models.ForeignKey(Model, on_delete=models.deletion.CASCADE, null=False)
    store_name = models.CharField("store_name", max_length=255, null=True, blank=True)
    elastic_index = models.CharField(
        "elastic_index", max_length=244, null=True, blank=True
    )
    elastic_index_answers = models.CharField(
        "elastic_index_answers", max_length=244, null=True, blank=True
    )
    elastic_index_eval_docs = models.CharField(
        "elastic_index_eval_docs", max_length=244, null=True, blank=True
    )
    elastic_index_labels = models.CharField(
        "elastic_index_labels", max_length=244, null=True, blank=True
    )
    trained_model_ref_url = models.CharField(
        "trained_model_ref_url", max_length=244, null=True, blank=True
    )
    trained_model_path = models.CharField(
        "trained_model_path", max_length=244, default="", blank=True
    )
    retreiver_count = models.IntegerField("retreiver_count", default=10)
    reader_count = models.IntegerField("reader_count", default=5)
    # hash to verify the integrity of the files
    files_hash = models.CharField("files_hash", max_length=244, null=True, blank=True)
    files_ready = models.BooleanField("files_ready", default=True)
    vote = models.BooleanField("vote", default=False)

    preprocessing_options = models.CharField(
        "preprocessing_options",
        choices=preprocessing_optionss,
        max_length=255,
        default=preprocessing_optionss[1][0],
    )
    split_overlap = models.IntegerField("split_overlap", default=5)
    split_length = models.IntegerField("split_length", default=10)
    split_respect_sentence_boundary = models.BooleanField(
        "split_respect_sentence_boundary"
    )
    split_by = models.CharField(
        "split_by", max_length=244, choices=splitting, default=splitting[0][0]
    )

    class Meta:
        db_table = "qa_project_db"


def upload_path_handler(instance, filename):
    fn, ext = os.path.splitext(filename)
    project = Project.objects.get(id=instance.project_f_id)
    return "{uuid}/documents/{ext}/{fname}".format(
        uuid=project.uuid, ext=ext[1:], fname=filename
    )


class File(models.Model):
    project_f = models.ForeignKey(
        Project, on_delete=models.deletion.CASCADE, null=False
    )
    file_f = models.FileField(
        null=True,
        upload_to=upload_path_handler,
        blank=True,
        validators=[FileExtensionValidator(["pdf", "txt", "docx"]), file_size],
    )
    file_name = models.CharField("file_name", max_length=255, default="", blank=True)
    extension = models.CharField("extension", max_length=255, default="", blank=True)
    file_size = models.FloatField("file_size", default=0)
    create_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        from .utils import valid_filename

        fn, ext = os.path.splitext(self.file_f.name)
        self.file_name = valid_filename(self.file_f.path.split("/")[-1])
        self.file_size = self.file_f.size
        self.extension = ext[1:]
        super(File, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if os.path.exists(self.file_f.path):
            os.remove(self.file_f.path)
        try:
            Delete_answers_from_elasticSearch(
                self.project_f.elastic_index_answers, None, self.file_name
            )
        except:
            pass
        super(File, self).delete(*args, **kwargs)

    class Meta:
        db_table = "qa_file_db"


class Status(enum.Enum):
    idle = 0
    running = 1
    finished = 2
    failed = 3
    aborted = 4


class Actions(enum.Enum):
    start = 1
    stop = 2


class Training_Job(models.Model):
    # ADD HARDWARE (CPU OR GPU)
    status_choices = (
        (Status.idle.value, "Idle"),
        (Status.running.value, "Running"),
        (Status.finished.value, "Finished"),
        (Status.failed.value, "Failed"),
        (Status.aborted.value, "Aborted"),
    )
    name = models.CharField("name", max_length=255)
    project = models.ForeignKey(Project, on_delete=models.deletion.CASCADE)
    status = models.IntegerField(
        "status", choices=status_choices, default=Status.idle.value
    )
    per_gpu_batch_size = models.IntegerField("per_gpu_batch_size", default=10)
    learning_rate = models.FloatField("learning_rate", default=0.00001)
    warmup_steps = models.IntegerField("warmup_steps", default=1)
    num_epochs = models.IntegerField("num_epochs", default=2)
    celery_task_id = models.CharField(
        "celery_task_id", max_length=244, default="", blank=True
    )
    create_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_job_db"


class Training_Job_Monitoring(models.Model):
    training_job = models.ForeignKey(Training_Job, on_delete=models.deletion.CASCADE)
    cpu_utilization = models.FloatField("cpu_utilization", default=0.0)
    memory_utilization = models.FloatField("memory_utilization", default=0.0)
    memory_utilization_size = models.FloatField("memory_utilization_size", default=0.0)
    disk_utilization = models.CharField("disk_utilization", default="", max_length=255)
    loop_count = models.IntegerField("loop_count", default=0)
    validation_accuracy = models.FloatField("validation_accuracy", default=0.0)
    training_accuracy = models.FloatField("training_accuracy", default=0.0)
    precision = models.FloatField("precision", default=0.0)
    f1_score = models.FloatField("f1_score", default=0.0)
    recall = models.FloatField("recall", default=0.0)
    number_of_steps = models.IntegerField("number_of_steps", default=0)
    sas = models.FloatField("sas", default=0.0)
    create_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "training_job_monitoring_db"
