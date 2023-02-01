from django.conf import settings
from haystack.document_stores import ElasticsearchDocumentStore
from elasticsearch import Elasticsearch
from elasticsearch import helpers


# Function to connect to Elastic Search
# return document_store (elastic search connection object)
def Elastic_Search_Connection(Project_uuid, label_index):

    document_store = ElasticsearchDocumentStore(
        host=settings.ELASTIC_HOST,
        username=settings.ELASTIC_USERNAME,
        password=settings.ELASTIC_PASSWORD,
        index=str(Project_uuid),
        label_index=label_index,
        embedding_field="emb",
        embedding_dim=768,
        excluded_meta_data=["emb"],
    )
    return document_store


# Function to connect to Elastic Search Natively
# return elastic_Search (elastic search connection object)
def Elastic_search_Connection_Native():
    elastic_Search = Elasticsearch(
        [{"host": "elasticsearch", "port": 9200}],
        http_auth=("admin", "elasticadmin"),
        use_ssl=False,
        verify_certs=False,
    )
    return elastic_Search


# Function to create a new index in Elastic Search
# return True if index is created successfully
def Create_Elastic_Index_answers(index_name):
    mapping = """
{
  "mappings": {
    "properties": {
      "document_id": {
        "type": "text"
      },
      "query": {
        "type": "text"
      },
      "answer": {
        "type": "text"
      },
        "score": {
        "type": "float"
        },
        "chosen": {
        "type": "boolean"
        },
        "offsets_in_document_start": {
        "type": "integer"
        },
        "offsets_in_document_end": {
        "type": "integer"
        },
        "context": {
        "type": "text"
        }
    }
  }
}"""
    elastic_Search = Elastic_search_Connection_Native()
    index_exists = elastic_Search.indices.exists(index=index_name)
    if not index_exists:
        elastic_Search.indices.create(index=index_name, body=mapping)
    return True


# Function to insert data in Elastic Search
# return True if data is inserted successfully
def insert_elastic_search_answers(index_name, data):
    elastic_Search = Elastic_search_Connection_Native()
    helpers.bulk(elastic_Search, data, index=index_name)
    return True


# Function to build query for Elastic Search
# return query (elastic search query object)
def query_builder(field, value=None, size=None):
    query = {
        "query": {"query_string": {"query": str(value), "default_field": str(field)}},
        "size": size,
        "from": 0,
        "sort": [],
    }
    return query
