import hashlib
import time
from elasticsearch.helpers import scan
from api.qa.elasticsearchStore.elasticsearch import (
    Elastic_search_Connection_Native,
    query_builder,
)

# Function to convert a list of answers to a list of elastic search objects (data)
# return elasticSearch_data (list of answers)
def answers_to_elasticSearch(data):
    elasticSearch_data = []
    try:
        for answer in data["answers"]:

            elasticSearch_data.append(
                {
                    "_id": hashlib.sha256(
                        answer["answer"].encode("utf-8")
                        + data["query"].encode("utf-8")
                        + str(answer["score"]).encode("utf-8")
                        + answer["context"].encode("utf-8")
                    ).hexdigest(),
                    "document_id": answer["document_id"],
                    "query": data["query"],
                    "answer": answer["answer"],
                    "score": answer["score"],
                    "chosen": answer["chosen"],
                    "offsets_in_document_start": answer["offsets_in_context"][0][
                        "start"
                    ],
                    "offsets_in_document_end": answer["offsets_in_context"][0]["end"],
                    "context": answer["context"],
                    "documentName": answer["meta"]["name"],
                    "Date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                }
            )
    except:
        pass

    return elasticSearch_data


# Function to get all answers from Elastic Search
# return elasticSearch_data (list of answers)
def Get_answers_list_from_elasticSearch(indice_list, page_size):
    query = query_builder("*", "*", 10000)
    temp = []
    elastic_Search = Elastic_search_Connection_Native()
    rel = scan(
        client=elastic_Search,
        query=query,
        index=indice_list,
        raise_on_error=True,
        preserve_order=False,
    )
    # Keep response in a list.
    result = list(rel)
    for hit in result:
        hit["_source"]["id"] = hit["_id"]
        hit["_source"]["index"] = hit["_index"]
        temp.append(hit["_source"])
    return temp


# Function to Delete answers from Elastic Search
# return true if deleted, false if not
def Delete_answers_from_elasticSearch(index, ids=None, file=None):
    elastic_Search = Elastic_search_Connection_Native()
    if file is None:
        try:
            for id in ids:
                elastic_Search.delete(index=index, id=id)
            return True
        except:
            return False
    else:
        query = {"query": {"match": {"documentName": file}}}
        elastic_Search.delete_by_query(index=index, body=query)


# Function to update answers in Elastic Search
# return true if updated, false if not
def Update_answers_from_elasticSearch(index, id, data):
    source_to_update = {"doc": {"chosen": data}}

    elastic_Search = Elastic_search_Connection_Native()
    try:
        elastic_Search.update(index=index, id=id, body=source_to_update)
        return True
    except:
        return False


# Function to get all answers chosen from Elastic Search
# return object (number of answers chosen,rejected answers, total answers)
def Get_Answer_Count_By_Chosen(index):
    query = {"query": {"bool": {"must": {"term": {"chosen": True}}}}}
    elastic_Search = Elastic_search_Connection_Native()
    try:
        index_exists = elastic_Search.indices.exists(index=index)
        if index_exists is True:
            data = elastic_Search.search(index=index, body=query)
            Total = Get_All_Documents_Count(index)
            chosen_ones = data["hits"]["total"]["value"]
            Rejected_ones = Total - chosen_ones
            return {"chosen": chosen_ones, "rejected": Rejected_ones, "total": Total}
        else:
            return {"chosen": 0, "rejected": 0, "total": 0}
    except:
        return {"chosen": 0, "rejected": 0, "total": 0}


# Function to get all answers count from Elastic Search
# return number (number of answers)
def Get_All_Documents_Count(index):
    elastic_Search = Elastic_search_Connection_Native()
    try:
        data = elastic_Search.count(index=index)
        return data["count"]
    except:
        return 0
