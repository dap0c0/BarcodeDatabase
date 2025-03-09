import time
from enum import Enum
GROCERY_NAME = "grocery"
HOME_BEAUTY_BABY_NAME = "home-beauty-baby"
JF_NAME = "joe-fresh"

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

# TODO: remove this! will be deprecated after
# reformatting code with DateFormatter
TIME_FORMAT = "%Y-%m-%d"

# TODO: Remove this!
def today():
    return time.strftime(TIME_FORMAT)
