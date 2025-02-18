from MongoClient import MongoClientAsync
from abc import ABC, abstractmethod
import json

class ProductUploader(ABC):
    UPSERT = True
    def __init__(self, isuri: str, database: str, collection: str, filename: str, debug: bool=False):
        assert isinstance(filename, str)
        assert isinstance(isuri, str)
        self._filename = filename
        self._database = database
        self._collection = collection
        self._debug = debug
        self._client = MongoClientAsync(isuri)
        self._client.select_collection(database, collection)

    @abstractmethod
    async def push_changes(self, query_filter_name: str):
        pass

    @abstractmethod
    async def get_products(self):
        pass

class JSONProductUploader(ProductUploader):
    ''' Allow client to write changes to a file
    and have those changes pushed to the item server.'''

    DEFAULT_QUERY_FILTER = "_id"
    DEFAULT_OUTPUT_FILENAME = "products.json"
    DEFAULT_INDENT = 4
    def __init__(self, isuri: str, database: str, collection: str, debug: bool=False, filename: str=DEFAULT_OUTPUT_FILENAME,):
        ProductUploader.__init__(self, isuri, database, collection, filename, debug)

    async def push_changes(self, query_filter_name: str=DEFAULT_QUERY_FILTER):
        assert isinstance(query_filter_name, str)
        assert query_filter_name != ""

        with open(self._filename, "r") as rfile:
            data_dict = json.load(rfile)
            doc_pairs = []

            for _, item in data_dict.items():
                assert isinstance(item, dict), f"{item} is not a dict!"
                query_filter = {query_filter_name: item[query_filter_name]}
                data_to_push = item
                doc_pairs.append((query_filter, data_to_push, self.UPSERT))

            if self._debug:
                print(f"Pushing {len(doc_pairs)} products to {self._database}.{self._collection}...")

            await self._client.bulk_replace(doc_pairs)
            print(f"Success!")

    async def get_products(self):
        product_json = {}
        cursor = await self._client.find({})

        async for item in cursor:
            assert isinstance(item, dict)
            product_json[item["_id"]] = item

        if self._debug:
            print(f"Got {len(product_json)} product(s)!")
        
        with open(self._filename, "w") as wfile:
            json.dump(product_json, wfile, indent=self.DEFAULT_INDENT)

            if self._debug:
                print(f"Dumped json to {self._filename}")
