from abc import ABC, abstractmethod
import pymongo
import json

class MongoClient(ABC):
    def __init__(self,
                 endpoint_uri: str):
        self._endpoint_uri = endpoint_uri

        # Attempt to connect to server
        self._client = pymongo.MongoClient(endpoint_uri)

        # Allow selection of collection
        self._collection = None

    @abstractmethod
    def select_collection(self,
                           database: str,
                           collection: str):
        pass

    @abstractmethod
    def insert_one(self,
                  document: dict):
        pass

    @abstractmethod
    def insert_many(self,
                   documents: list):
        pass

    @abstractmethod
    def replace_one(self,
                    query_filter: dict,
                    document: dict,
                    upsert: bool):
        pass

    def _verify_collection(self):
        assert self._collection != None, "The collection is unselected!"

class MongoClientSync(MongoClient):
    def select_collection(self,
                           database: str,
                           collection: str):
        assert isinstance(database, str)
        assert isinstance(collection, str)
        # breakpoint()
        collection = self._client[database][collection]
        self._collection = collection

    # Insertions
    def insert_one(self,
                  document: dict):
        assert isinstance(document, dict)
        self._verify_collection()
        return self._collection.insert_one(document)

    def insert_many(self,
                    documents: list):
        assert isinstance(documents, list)

        for document in documents:
            assert isinstance(document, dict)

        return self._collection.insert_many(documents)

    # Replacement
    def replace_one(self,
                    query_filter: dict,
                    document: dict,
                    upsert: bool):
        assert isinstance(query_filter, dict)
        assert isinstance(document, dict)
        assert isinstance(upsert, bool)
        self._verify_collection()
        return self._collection.replace_one(query_filter,
                                   document,
                                    upsert)

class MongoClientAsync(MongoClient):
    pass
