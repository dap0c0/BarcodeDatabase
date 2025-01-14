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

    @abstractmethod
    def bulk_replace(self,
                     document_pairs: list):
        pass

    @abstractmethod
    def create_index(self,
                     key: str):
        pass

    def select_collection(self,
                           database: str,
                           collection: str):
        assert isinstance(database, str)
        assert isinstance(collection, str)
        collection = self._client[database][collection]
        self._collection = collection

    def _verify_collection(self):
        assert self._collection != None, "The collection is unselected!"

class MongoClientAsync(MongoClient):
    def __init__(self,
                 endpoint_uri: str):
        self._endpoint_uri = endpoint_uri

        # Attempt to connect to server
        self._client = pymongo.AsyncMongoClient(endpoint_uri)

        # Allow selection of collection
        self._collection = None

    # Insertion
    async def insert_one(self,
                        document: dict):
        assert isinstance(document, dict)
        self._verify_collection()
        return await self._collection.insert_one(document)

    async def insert_many(self,
                          documents: list):
        assert isinstance(documents, list)
        
        for document in documents:
            assert isinstance(document, list)

        return await self._collection.insert_many(documents)

    # Replacement
    async def replace_one(self,
                    query_filter: dict,
                    document: dict,
                    upsert: bool):
        assert isinstance(query_filter, dict)
        assert isinstance(document, dict)
        assert isinstance(upsert, bool)
        self._verify_collection()
        return await self._collection.replace_one(query_filter,
                                   document,
                                    upsert)
    async def bulk_replace(self,
                     document_pairs: list):
        assert isinstance(document_pairs, list)
        self._verify_collection()
        operations = []

        for triplet in document_pairs:
            assert isinstance(triplet, tuple), f"{triplet} is not a tuple!"
            assert len(triplet) == 3, f"Tuple should be of length 3."
            query, data, upsert = triplet
            assert isinstance(query, dict)
            assert isinstance(data, dict)
            assert isinstance(upsert, bool)
            operations.append(pymongo.ReplaceOne(query, data, upsert))

        # Start bulk write
        return await self._collection.bulk_write(operations)

    # Indexing
    async def create_index(self,
                     key: str):
        assert isinstance(key, str)
        self._verify_collection()
        return await self._collection.create_index(key)

class MongoClientSync(MongoClient):
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
    def bulk_replace(self,
                     document_pairs: list):
        assert isinstance(document_pairs, list)
        self._verify_collection()
        operations = []

        for triplet in document_pairs:
            assert isinstance(triplet, tuple), f"{triplet} is not a tuple!"
            assert len(triplet) == 3, f"Tuple should be of length 3."
            query, data, upsert = triplet
            assert isinstance(query, dict)
            assert isinstance(data, dict)
            assert isinstance(upsert, bool)
            operations.append(pymongo.ReplaceOne(query, data, upsert))

        # Start bulk write
        return self._collection.bulk_write(operations)


    
    # Indexing
    def create_index(self,
                     key: str):
        assert isinstance(key, str)
        self._verify_collection()
        return self._collection.create_index(key)
