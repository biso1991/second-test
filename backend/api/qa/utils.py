from api.qa.elasticsearchStore.elasticsearch import (
    Elastic_search_Connection_Native,
    query_builder,
)
from api.qa.models import File, Model
import hashlib
from django.conf import settings
import os
import string
import spacy
import pandas as pd
from haystack.utils import SquadData

# Function to return the training data path from project uuid
def folder(uuid):
    path = "{}{}/{}".format(
        settings.MEDIA_URL, str(uuid), settings.TRAINING_DATA_DIR
    ).strip("/")
    if not os.path.exists(path):
        os.makedirs(path)
    return path


# function to get the subject from the context
def get_subject_phrase_context(context):
    punctuation = set(string.punctuation)
    context = "".join(ch for ch in context if ch not in punctuation)
    try:
        nlp = spacy.load("en_core_web_sm")
        doc = nlp(context)
        for token in doc:
            if "subj" in token.dep_:
                subtree = list(token.subtree)
                start = subtree[0].i
                end = subtree[-1].i + 1
                return doc[start:end].text
        return ""
    except:
        return ""


# function to get the id of documents from answers
# return documents with name,score and id
def Format_average_documents(documents, project=None):
    list_document = []
    for document in documents:
        idFile = -1
        listFIles = File.objects.filter(project_f=project.id)
        for file in listFIles:
            file_name = os.path.basename(file.file_f.name)
            if file_name == document["meta"]["name"]:
                idFile = file.id
        list_document.append(
            {
                "score": document["score"],
                "name": document["meta"]["name"],
                "id": idFile,
            }
        )
    df = pd.DataFrame(list_document, columns=["score", "name", "id"])
    new_data_groupby = df.groupby(["name"]).mean()
    new_data_groupby_list = new_data_groupby.to_dict("index")
    result_list = []
    for key, value in new_data_groupby_list.items():
        result_list.append(
            {"name": key, "score": value.get("score"), "id": value.get("id")}
        )
    return result_list


# Function to create a hash from files name
def get_hash(project):
    files = File.objects.filter(project_f=project)
    files_text = ""
    for file in files:
        files_text += file.file_f.name
    return hashlib.md5(files_text.encode()).hexdigest()


# function to verify if the files of a project has been changed
def is_files_changed(project):
    hash_file = project.files_hash
    new_hash_file = get_hash(project)
    if hash_file == new_hash_file:
        return False
    else:
        project.files_hash = new_hash_file
        project.save()
        return True


# Function to generate a squad file from answers
# return true if the file is generated and exception if not
def answers_to_squad_format(project):
    query = query_builder("chosen", "true", 10000)
    data = Elastic_search_Connection_Native().search(
        index=project.elastic_index_answers, body=query
    )["hits"]["hits"]
    file_name = project.uuid
    squad_answers = []

    for answer in data:
        if answer["_source"]["chosen"] == True:
            squad_answers.append(
                {
                    "title": get_subject_phrase_context(answer["_source"]["context"]),
                    "context": answer["_source"]["context"],
                    "question": answer["_source"]["query"],
                    "id": answer["_source"]["document_id"],
                    "answer_text": answer["_source"]["answer"],
                    "answer_start": answer["_source"]["offsets_in_document_start"],
                    "is_impossible": False,
                }
            )
    sq = SquadData({"data": {}})
    df = pd.DataFrame(
        squad_answers,
        columns=[
            "title",
            "context",
            "question",
            "id",
            "answer_text",
            "answer_start",
            "is_impossible",
        ],
    )
    if len(squad_answers) > 0:
        squad_docs = sq.df_to_data(df)
        sq = SquadData({"data": squad_docs, "version": 0.1})
        # create directory if not exists
        path_directory = folder(project.uuid)
        path_training = "{}/{}.json".format(path_directory, file_name)
        sq.save(path_training)
        return True
    else:
        raise Exception("No answers found")


# function to create zip file (trained model)
# return zip file path
def Create_Zip_File(path_model):
    from os import listdir
    from os.path import isfile, join
    import zipfile

    filenames = [
        f
        for f in listdir(path_model)
        if (isfile(join(path_model, f))) and (not f.endswith(".zip"))
    ]
    zip_file_path = "{}/{}".format(path_model, settings.ZIP_FILE_NAME_MODEL)
    zip_file = zipfile.ZipFile(zip_file_path, "w")
    for file in filenames:
        filename = os.path.basename(os.path.normpath(file))
        file = "{}/{}".format(path_model, os.path.basename(os.path.normpath(file)))
        zip_file.write(file, filename)
    zip_file.close()
    return zip_file_path


# Function to download a model from Hugging Face name of repository
# return obeject (local,path,uuid)
def Download_HuggingFace_Model(repo_id_url):
    import uuid

    uuid_model = uuid.uuid4().hex
    directory = "{}/{}".format(settings.ROOT_MODELS_DIR, uuid_model)
    return_value = {}
    try:
        # If the model is already downloaded, then return the path
        model = Model.objects.get(model_ref_url=repo_id_url)
        if isinstance(model, Model):
            return_value = {
                "local": True,
                "path": model.model_ref_path,
                "uuid": model.uuid,
            }
        else:
            return_value = {
                "local": True,
                "path": model[0].model_ref_path,
                "uuid": model[0].uuid,
            }
    except:
        from haystack.nodes import FARMReader

        reader = FARMReader(
            model_name_or_path=repo_id_url,
            use_gpu=True,
            progress_bar=True,
            force_download=False,
        )
        reader.save(directory=directory)
        return_value = {"local": False, "path": directory, "uuid": uuid_model}
    return return_value


# Extract the model from the zip file Uploaded by the user
# return path of the model
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


# Function to get the highest depth of the directory tree
# return path of the model
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


# Function to generate a valid filename
# return generated filename
def valid_filename(s):
    file_n = File()
    File_Name = file_n.file_f.storage.generate_filename(s)
    return File_Name


# function to verify huggingFace name of repository
# return True or False
def verifyHuggingFaceUrl(url):
    import requests

    url = "https://huggingface.co/" + url
    response = requests.request("GET", url, headers={}, data={})
    if response.status_code == 200:
        return True
    else:
        return False
