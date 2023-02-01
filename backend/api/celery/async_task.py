from time import sleep
from django.conf import settings
from api.celery.celery import app as celery_app
from api.qa import utils
from api.qa.elasticsearchStore.elasticsearch import Elastic_Search_Connection
from api.qa.models import Model, Project, Status, Training_Job, Training_Job_Monitoring
from haystack.utils import convert_files_to_docs
from api.qa.monitoring_class import Monitor
from api.qa.redis.models import Task, type_task
from api.qa.redis.task_service import TaskService
from api.qa.task_service import Send_Status
from haystack.preprocessor.preprocessor import PreProcessor
from haystack.nodes import FARMReader, BM25Retriever
from haystack.pipelines import ExtractiveQAPipeline
from django.core.cache import cache
import gc
import os


# ReaderRetreiver Function
# return ExtractiveQAPipeline/FARMReader
def ReaderRetreiver(
    document_store, model_ref_Path, no_answer=None, topK=None, training=None
):
    if training == True:
        reader = FARMReader(
            model_name_or_path=model_ref_Path, use_gpu=True, num_processes=1
        )
        return reader
    if no_answer == None:
        retriever = BM25Retriever(document_store=document_store)
        reader = FARMReader(
            model_name_or_path=model_ref_Path,
            use_gpu=True,
            progress_bar=True,
            force_download=False,
        )
    else:
        # BM25Retriever is for evaluation
        retriever = BM25Retriever(document_store=document_store)
        reader = FARMReader(
            model_name_or_path=model_ref_Path,
            top_k=topK,
            return_no_answer=True,
            # num_processes=1,
        )
    pipe = ExtractiveQAPipeline(reader, retriever)
    return pipe


# Preprocessor Function
# retrun Preprocessor with params
def Preprocessor_Haystack(Project_Object, eval=None):
    if eval == None:
        if Project_Object.preprocessing_options == "sliding-window":
            preprocessor = PreProcessor(
                clean_empty_lines=True,
                split_by=Project_Object.split_by,
                split_respect_sentence_boundary=Project_Object.split_respect_sentence_boundary,
                split_overlap=Project_Object.split_overlap,
                split_length=Project_Object.split_length,
            )
        elif Project_Object.preprocessing_options == "simple-text-splitting":
            preprocessor = PreProcessor(
                clean_empty_lines=True,
                clean_whitespace=True,
                split_by=Project_Object.split_by,
                split_respect_sentence_boundary=Project_Object.split_respect_sentence_boundary,
                split_length=Project_Object.split_length,
            )
    elif eval == True:
        preprocessor = PreProcessor(
            split_length=200,
            split_overlap=0,
            split_respect_sentence_boundary=False,
            clean_empty_lines=False,
            clean_whitespace=False,
        )
    return preprocessor


# Update Training Job Status
def training_job_status(training_job, status):
    training_job.status = status
    training_job.save()


# Async Task Function to Preprocess Documents of a project
@celery_app.task(
    default_retry_delay=30, max_retries=15, soft_time_limit=1000, time_limit=100000
)
def convert_file_to_dict(doc_dir, project):
    task_id = ""
    try:
        try:
            Project_object = Project.objects.get(id=project)
        except:
            # training_job_status(Training_job, Status.failed.value)
            return {"dicts": None, "result": "No project found"}
        user_id = Project_object.owner.id
        taskService = TaskService(str(user_id))
        task = Task(
            type_task.preprocessing.value, Project_object.id, -1, Project_object.name
        )
        task_id = taskService.AddRunningTasks(task)
        Send_Status({"task": task, "status": Status.running.value})
        try:
            Model_object = Model.objects.get(id=Project_object.model.id)
        except:
            Send_Status({"task": task, "status": Status.failed.value})
            taskService.deleteRunningTasks(task_id)
            return {"dicts": None, "result": "No model found"}
        # training_job_status(Training_job, Status.running.value)
        document_store = Elastic_Search_Connection(
            Project_object.uuid, Project_object.elastic_index_labels
        )
        preprocessor = Preprocessor_Haystack(Project_object)
        lists = convert_files_to_docs(dir_path=doc_dir, split_paragraphs=True)
        nested_docs = [preprocessor.process(d) for d in lists]
        docs = [d for x in nested_docs for d in x]
        document_store.write_documents(docs)
        try:
            ReaderRetreiver(document_store, Model_object.model_ref_path)
        except:
            pass
        # training_job_status(Training_job, Status.finished.value)
        Project_object.files_ready = True
        Project_object.save()
        Send_Status({"task": task, "status": Status.finished.value})
        taskService.deleteRunningTasks(task_id)
        return {"result": True}
    except:
        Send_Status({"task": task, "status": Status.failed.value})
        taskService.deleteRunningTasks(task_id)
        return {"result": False}


# Evaluation Function to Evaluate Training Job
# return True/False + Training Job Monitoring Object
def Haystack_QA_Evalution(
    project, training_job, path_data_training, New_tarining_Job_Monitoring
):
    document_store = Elastic_Search_Connection(
        project.uuid, project.elastic_index_labels
    )
    preprocessor = Preprocessor_Haystack(training_job, True)
    # ADD EVALUATION TO DOCUMENT STORE
    document_store.add_eval_data(
        filename=path_data_training,
        doc_index=project.elastic_index_eval_docs,
        label_index=project.elastic_index_labels,
        preprocessor=preprocessor,
    )
    if project.trained_model_path != "":
        model_ref_path = project.trained_model_path
    else:
        model_ref_path = project.model.model_ref_path
    pipeline = ReaderRetreiver(
        document_store, model_ref_path, True, project.reader_count
    )
    eval_labels = document_store.get_all_labels_aggregated(
        drop_negative_labels=True, drop_no_answers=True
    )
    # {'Retriever': {
    #      'recall_multi_hit': 0.43333333333333335, (RATIO OF MULTI HIT DOCS) (0 to 1)
    #      'recall_single_hit': 0.6666666666666666, (RATIO OF SINGLE HIT DOCS) (0 to 1)
    #     (validation_accuracy) 'map': 0.12435185185185187, (0 to 1) (Average Precision indicates whether your model can correctly identify all the positive examples without accidentally marking too many negative examples as positive.)
    #      'precision': 0.16666666666666666, (0 to 1) [    (TP + TN)/(P + N)   ] )
    #      'mrr': 0.15277777777777776, (number of correct answers / total number of answers) (0 to 1) (training accuracy)
    #      'ndcg': 0.23443403708553204
    #     }, 'Reader': 'f1': 0.7619047619047619, (recall,precision) TRUE AND FALSE (0 to 1)
    #        'exact_match': 0.6666666666666666 () , (RATIO OF TRUE POSITIVE - very STRICT) (0 to 1)
    # recall = (f1*precision)/((2*precision)-f1)
    # F1 = 2*(precision*recall)/(precision+recall)
    training_Job_Monitoring = Training_Job_Monitoring.objects.get(
        id=New_tarining_Job_Monitoring
    )
    advanced_eval_result = pipeline.eval(
        labels=eval_labels,
        params={"Retriever": {"top_k": project.retreiver_count}},
        sas_model_name_or_path="cross-encoder/stsb-roberta-large",
    )
    metrics = advanced_eval_result.calculate_metrics()
    f1_eval = metrics["Reader"]["f1"]
    F1_val = f1_eval.item()
    sas_eval = metrics["Reader"]["sas"]
    sas_val = sas_eval.item()
    training_Job_Monitoring.sas = sas_val
    training_Job_Monitoring.validation_accuracy = metrics["Retriever"]["map"]
    training_Job_Monitoring.training_accuracy = metrics["Retriever"]["mrr"]
    training_Job_Monitoring.precision = metrics["Retriever"]["precision"]
    training_Job_Monitoring.recall = metrics["Retriever"]["recall_multi_hit"]
    if round(F1_val, 15) != training_Job_Monitoring.f1_score:
        training_Job_Monitoring.f1_score = round(F1_val, 15)
        training_Job_Monitoring.save()
        gc.collect()
        return {"result": False, "training_job_monitoring": training_Job_Monitoring}
    elif round(F1_val, 15) == training_Job_Monitoring.f1_score:
        gc.collect()
        return {"result": True, "training_job_monitoring": training_Job_Monitoring}


# Training Function to Train Model
def Reader_Training(
    project,
    training_job,
    training_data_path,
    training_file,
    path_model,
    New_tarining_Job_Monitoring,
):
    model_path_ = ""
    training_Job_Monitoring = Training_Job_Monitoring.objects.get(
        id=New_tarining_Job_Monitoring
    )
    if project.trained_model_path != "":
        model_path_ = project.trained_model_path
    else:
        model_path_ = Model.objects.get(id=project.model.id).model_ref_path

    reader = ReaderRetreiver(None, model_path_, training=True)
    reader.train(
        num_processes=1,
        data_dir=training_data_path,
        train_filename=training_file,
        use_gpu=True,
        batch_size=training_job.per_gpu_batch_size,
        learning_rate=training_job.learning_rate,
        n_epochs=training_job.num_epochs,
        # warmup_proportion=training_job.warmup_steps,
    )
    reader.save(directory=path_model)
    Zip_File_Model = utils.Create_Zip_File(path_model)
    project.trained_model_ref_url = "{}/{}".format(settings.ROOT_URL, Zip_File_Model)

    training_Job_Monitoring.number_of_steps += 1
    training_Job_Monitoring.save()
    if project.trained_model_path != path_model:
        project.trained_model_path = path_model
    project.save()
    # gc.collect()
    return None


# Async Function to Train Model in celery
# return number of steps (loop_count)
@celery_app.task(
    default_retry_delay=30, max_retries=15, soft_time_limit=100000, time_limit=100000
)
def Training_Loop_Async(
    training_job_id,
    project_id,
    training_data_path,
    training_file,
    path_model,
    path_data_training,
    New_tarining_Job_Monitoring,
):
    # try:
    i = 0
    try:
        training_job = Training_Job.objects.get(id=training_job_id)
    except:
        return {"result": "Training Job Not Found"}
    sleep(1)
    try:
        project = Project.objects.get(id=project_id)
    except:
        training_job.status = Status.finished.value
        training_job.save()
        return {"result": "Project Not Found"}
    training_Job_Monitoring = Training_Job_Monitoring.objects.get(
        id=New_tarining_Job_Monitoring
    )
    monitor = Monitor(
        os.getpid(), training_job, str(project.uuid), training_Job_Monitoring
    )
    monitor.start()
    user_id = project.owner.id
    taskService = TaskService(str(user_id))
    task = Task(type_task.training.value, project.id, training_job.id, project.name)
    task_id = taskService.AddRunningTasks(task)
    Send_Status({"task": task, "status": Status.running.value})
    training_job.status = Status.running.value
    training_job.save()
    Reader_Training(
        project,
        training_job,
        training_data_path,
        training_file,
        path_model,
        New_tarining_Job_Monitoring,
    )
    result_eval = {}
    result_eval["result"] = False
    while result_eval["result"] == False:
        if cache.get(training_job.celery_task_id) is not None:
            Send_Status({"task": task, "status": Status.aborted.value})
            taskService.deleteRunningTasks(task_id)
            training_job.status = Status.aborted.value
            training_job.save()
            cache.delete(training_job.celery_task_id)
            training_info = monitor.stop()
            training_Job_Monitoring.cpu_utilization = training_info["cpu_utilization"]
            training_Job_Monitoring.memory_utilization = training_info[
                "memory_utilization"
            ]
            training_Job_Monitoring.memory_utilization_size = training_info[
                "memory_utilization_size"
            ]
            training_Job_Monitoring.disk_utilization = training_info["disk_utilization"]
            training_Job_Monitoring.loop_count = i
            training_Job_Monitoring.save()
            # gc.collect()
            break
        i += 1
        result_eval = Haystack_QA_Evalution(
            project, training_job, path_data_training, New_tarining_Job_Monitoring
        )
        result_eval["training_job_monitoring"].loop_count = i
        monitor.update(result_eval["training_job_monitoring"])
        if result_eval["result"] == True:
            monitor.update(result_eval["training_job_monitoring"])
            Send_Status({"task": task, "status": Status.finished.value})
            taskService.deleteRunningTasks(task_id)
            training_job.status = Status.finished.value
            training_job.save()
            training_info = monitor.stop()
            training_Job_Monitoring.cpu_utilization = training_info["cpu_utilization"]
            training_Job_Monitoring.memory_utilization = training_info[
                "memory_utilization"
            ]
            training_Job_Monitoring.memory_utilization_size = training_info[
                "memory_utilization_size"
            ]
            training_Job_Monitoring.disk_utilization = training_info["disk_utilization"]
            training_Job_Monitoring.loop_count = i
            training_Job_Monitoring.save()
            # gc.collect()
            break
        Reader_Training(
            project,
            training_job,
            training_data_path,
            training_file,
            path_model,
            New_tarining_Job_Monitoring,
        )
    # gc.collect()
    return i
    # except:
    #     pass
