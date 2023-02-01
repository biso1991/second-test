from api.qa.elasticsearchStore.elasticsearch import Elastic_Search_Connection
import json
from api.qa.models import Model, Project, Training_Job_Monitoring
from django.conf import settings
from api.celery.async_task import (
    convert_file_to_dict,
    ReaderRetreiver,
    Training_Loop_Async,
)

# Function to start Preprocessing or QA pipeline
# return true if success, false if not for preprocessing
# return predictions (answers) if success from Pipeline/ false if not
def Preprocessing_QA(project, initial, query=None):
    project_UUID = str(project.uuid)
    Label_index = "{}-{}".format(project_UUID, settings.LABEL_INDEX_NAME)
    eval_docs_index = "{}-{}".format(project_UUID, settings.DOCS_EVAL_INDEX_NAME)
    project.elastic_index_labels = Label_index
    project.elastic_index_eval_docs = eval_docs_index
    project.save()

    document_store = Elastic_Search_Connection(project_UUID, Label_index)

    model_ref_path = Model.objects.get(id=project.model.id).model_ref_path

    if project.trained_model_path != "":
        model_ref_path = project.trained_model_path

    if initial == True:
        project.elastic_index = project_UUID
        project.save()
        doc_dir = "{}{}/documents/".format(settings.MEDIA_URL, project_UUID).strip("/")
        # Convert all files to dict and insert Splitted text to elasticsearch Asynchrounously
        convert_file_to_dict.apply_async(queue="", args=(doc_dir, project.id))
        return True

    if initial == False:
        pipe = ReaderRetreiver(document_store, model_ref_path)
        prediction = pipe.run(
            query="{}".format(query),
            params={
                "Retriever": {"top_k": project.retreiver_count},
                "Reader": {"top_k": project.reader_count},
            },
        )
        return json.dumps(prediction, default=vars)
    return False


# Function to start Training loop
# return object (result) true if success, false if not + id of celery task
def training_job_loop(training_job):
    try:
        project = Project.objects.get(id=training_job.project.id)
        training_data_path = "{}{}/{}".format(
            settings.MEDIA_URL, str(project.uuid), settings.TRAINING_DATA_DIR
        ).strip("/")
        path_model = "{}{}/{}".format(
            settings.MEDIA_URL, str(project.uuid), settings.MODEL_DIR
        ).strip("/")
        training_file = "{}.json".format(project.uuid)
        path_data_training = "{}/{}".format(training_data_path, training_file).strip(
            "/"
        )
        training_job_monitoring = Training_Job_Monitoring(training_job=training_job)
        # get id after save to get the id of the training_job_monitoring
        training_job_monitoring.save()
        id_celery_task = Training_Loop_Async.apply_async(
            queue="",
            args=(
                training_job.id,
                project.id,
                training_data_path,
                training_file,
                path_model,
                path_data_training,
                training_job_monitoring.id,
            ),
        )
        training_job.celery_task_id = id_celery_task
        training_job.save()
        return {"result": True, "id": id_celery_task.id}
    except:
        return {"result": False}
