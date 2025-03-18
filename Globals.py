import time
from enum import Enum
GROCERY_NAME = "grocery"
HOME_BEAUTY_BABY_NAME = "home-beauty-baby"
JF_NAME = "joe-fresh"

class Product:
    def __init__(self):
        self._id: str
        self.product_title: str
        self.product_brand: str
        self.product_url: str
        self.product_id: str
        self.product_package_size: str
        self.price_descriptor: str
        self.regular_price: str
        self.sale_price: str
        self.mop_price: str
        self.non_member_price: str
        self.before_price: str
        self.ean: str
        self.plu: str
        self.upc: str

    def as_dict(self):
        temp = dict()
        price_data = dict()
        code_data = dict()

        for field, value in self.__dict__.items():
            # Group price data
            if field == "regular_price" or \
                field == "sale_price" or \
                field == "mop_price" or \
                field == "non_member_price" or \
                field == "before_price":
                price_data[field] = value

            # Group code data
            elif field == "ean" or \
                field == "plu" or \
                field == "upc":
                code_data[field] = value

            else:
                temp[field] = value

        temp["prices"] = price_data
        temp["codes"] = code_data
        return temp

class Department(Enum):
    GROCERY_NAME = "grocery"
    HOME_BEAUTY_BABY_NAME = "home-beauty-baby"
    JF_NAME = "joe-fresh"

class ProductMapping(Enum):
    ''' Map column index for each field in spreadsheet'''
    _id = 1
    product_title = 2
    product_brand = 3
    product_url = 4
    product_id = 5
    product_package_size = 6
    price_descriptor = 7
    regular_price = 8
    sale_price = 9
    mop_price = 10
    non_member_price = 11
    before_price = 12
    ean = 13
    plu = 14
    upc = 15

    def get(x: str | int):
        assert isinstance(x, str) or isinstance(x, int)
        
        if isinstance(x, str):
            return ProductMapping.__dict__["_member_map_"][x]

        elif isinstance(x, int):
            return ProductMapping.__dict__["_value2member_map_"][x]

class Secrets(Enum):
    CF_TOKEN_FILE="cf_tunnel_token.txt"
    ISURI_FILE="item_server_url.txt"

    def get_isuri():
        with open(Secrets.ISURI_FILE.value, "r") as rfile:
            return rfile.read().strip()

# TODO: remove this! will be deprecated after
# reformatting code with DateFormatter
TIME_FORMAT = "%Y-%m-%d"

# TODO: Remove this!
def today():
    return time.strftime(TIME_FORMAT)
