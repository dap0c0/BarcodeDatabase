from MongoClient import MongoClientAsync
from abc import ABC, abstractmethod
import json
from openpyxl import Workbook
from Globals import ProductMapping
from string import ascii_uppercase

class ProductUploader(ABC):
    UPSERT = True
    DEFAULT_QUERY_FILTER = "_id"
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

class SpreadsheetProductUploader(ProductUploader):
    ''' Allow client to write changes to a spreadsheet
    and have those changes pushed to the item server.

    This class is a containment of JSONProductUploader, as
    it is necessary to convert all spreadsheet data
    into json before uploading.
    '''
    DEFAULT_FILENAME_SPREADSHEET = "products.xlsx"

    def __init__(self, isuri: str, database: str, collection: str, filename: str, debug: bool = False):
        self._json_uploader = JSONProductUploader(isuri, database, collection, debug, filename)
        self._isuri = isuri
        self._filename = filename
        self._debug = debug

    async def push_changes(self, query_filter_name: str=ProductUploader.DEFAULT_QUERY_FILTER):
        pass

    def get_products(self):
        workbook = self._json_to_workbook()
        workbook.save(filename=self.DEFAULT_FILENAME_SPREADSHEET)
        print(f"Spreadsheet saved as {self.DEFAULT_FILENAME_SPREADSHEET}")

    def _json_to_workbook(self) -> Workbook:
        ''' Convert all dictionaries from the json file to
        a workbook.'''
        workbook = Workbook()
        sheet = workbook.active

        # Initialize the field row
        for prod in ProductMapping:
            assert isinstance(prod.value, int)
            assert isinstance(prod.name, str)
            sheet[f"{self._int_to_alpha(prod.value)}1"] = prod.name

        # Append new products to the sheet
        curr_row = 2
        products_dict = self._get_products_json()

        for _, product in products_dict.items():
            for key, val in self._denest_dict(product).items():
                if isinstance(val, str):
                    column = ProductMapping.get(key).value
                    sheet[f"{self._int_to_alpha(column)}{curr_row}"] = val

            curr_row += 1
        return workbook

    def _workbook_to_dict(self, workbook: Workbook) -> dict:
        assert isinstance(workbook, Workbook)

    def _int_to_alpha(self, val: int) -> str:
        ''' Convert the integer value to its respective
        alphanumeric string. E.g.:
        1 -> "A"
        2 -> "B"
        26 -> "Z"
        27 -> "AA"
        28 -> ""AB"
        53 -> "BA"

        Treat the strings as if they were a base-26 system.'''
        assert isinstance(val, int)
        
        # TODO: provide functionality for int vals past 26
        if val >= 1:
            return ascii_uppercase[val - 1]

        raise ValueError(f"{val} isn't >= 1")

    def _denest_dict(self, dictionary: dict) -> dict:
        ''' Denest all dictionaries within the given dictionary and
            return a dictionary with all fields of non-dictionary
            class.'''
        assert isinstance(dictionary, dict)
        dicts_found = []
        denested_dict = {}

        # Iterate through each field to check if
        # a nested dictionary is present.
        for key, item in dictionary.items():
            if isinstance(item, dict):
                dicts_found.append(item)

            else:
                denested_dict[key] = item

        # Base case: the current dictionary doesn't contain
        # any nested dictionaries. Denested_dict is already
        # populated with the same fields as the original dictionary.
        if len(dicts_found) == 0:
            return denested_dict

        # Recursive case: the current dictionary contains >= 1
        # dictionary items.
        else:
            [denested_dict.update(self._denest_dict(d)) for d in dicts_found]
            return denested_dict
            
    def _get_products_json(self) -> dict:
        ''' Read from the json file and return
        all products in a dictionary.'''
        with open(self._filename, "r") as rfile:
            data_dict = json.load(rfile)
            return data_dict

class JSONProductUploader(ProductUploader):
    ''' Allow client to write changes to a json file
    and have those changes pushed to the item server.'''

    DEFAULT_OUTPUT_FILENAME = "products.json"
    DEFAULT_INDENT = 4
    def __init__(self, isuri: str, database: str, collection: str, debug: bool=False, filename: str=DEFAULT_OUTPUT_FILENAME):
        ProductUploader.__init__(self, isuri, database, collection, filename, debug)

    async def push_changes(self, query_filter_name: str=ProductUploader.DEFAULT_QUERY_FILTER):
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

uploader.get_products()
