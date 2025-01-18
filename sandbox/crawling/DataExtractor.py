from bs4 import BeautifulSoup
from bs4.element import Tag
import json

class DataExtractor():
    ''' A wrapper class that identifies the following given a product's
        html tag:
        - product title
        - product brand
        - product url
        - product id
        - product package size
            - price per weight
            - price per unit
        - price descriptor
        - current price
            - sale price
            - member price
            - non-member price
            - regular price'''

    # Product title identifier(s)
    PRODUCT_TITLE_ID = "css-6qrhwc"

    # Product brand identifier(s)
    PRODUCT_BRAND_ID = "css-1ecdp9w"

    # Product url identifier(s)
    PRODUCT_URL_ID = "css-1hnz6hu"

    # Product package size identifier(s)
    PRODUCT_PACKAGE_SIZE_ID = "css-1yftjin"

    # Price descriptor identifier(s)
    PRICE_DESCRIPTOR_ID = "css-1m5a6y8"

    # Current price identifier(s)
    SALE_PRICE_ID = "css-o93gbd"
    REGULAR_PRICE_ID = "css-pwnbcb"
    MOP_REGULAR_PRICE_ID = "css-o93gbd"
    NON_MEMBER_PRICE_ID = "css-1wji473"

    # Was price (striked-out price) identifier(s)
    WAS_PRICE_SALE_ID = "css-623q5h"
    WAS_NON_MEMBER_PRICE_ID = "css-esi4gg2"

    def __init__(self, element: Tag):
        assert isinstance(element, Tag), "The object to wrap is not a Tag!"
        self._element = element
        self.data = {
            "product_title": "",
            "product_brand": "",
            "product_url": "",
            "product_id": "",
            "product_package_size": "",
            "price_descriptor": "",
            "prices": {
                "regular_price": "",
                "sale_price": "",
                "mop_price": "",
                "non_member_price": "",
                "before_price": ""
                    }
                }

        # Start extracting data
        self.data["product_title"] = self._get_product_title()
        self.data["product_brand"] = self._get_product_brand()
        self.data["product_url"] = self._get_product_url()
        self.data["product_id"] = self._get_product_id()
        self.data["product_package_size"] = self._get_product_package_size()
        self.data["price_descriptor"] = self._get_price_descriptor()
        self.data["prices"] = self._get_price()

    def json(self, indents=4) -> str:
        ''' Return the json of the data.'''
        assert self.data != None
        return json.dumps(self.data, indent=indents)

    # <----- Helper Functions -----> #
    def _get_product_title(self) -> str:
        ''' Search the <h3> tag for the title.'''
        try:
            title_tag = self._element.find("h3", class_=f"chakra-heading {DataExtractor.PRODUCT_TITLE_ID}")
            return str(title_tag.string)
        except:
            return ""
            
    def _get_product_brand(self) -> str:
        try:
            brand_tag = self._element.find("p", class_=f"chakra-text {DataExtractor.PRODUCT_BRAND_ID}")
            return str(brand_tag.string)

        except:
            return ""

    def _get_product_url(self) -> str:
        try:
            url_tag = self._element.find("a", class_=f"chakra-linkbox__overlay {DataExtractor.PRODUCT_URL_ID}")
            return url_tag.attrs["href"]

        except:
            return ""
        
    def _get_product_id(self) -> str:
        ''' Search the <h3> tag for the id.'''
        try:
            title_tag = self._element.find("h3", class_=f"chakra-heading {DataExtractor.PRODUCT_TITLE_ID}")
            return title_tag.attrs["id"]

        except:
            return ""

    def _get_product_package_size(self) -> str:
        try:
            package_tag = self._element.find("p", class_=f"chakra-text {DataExtractor.PRODUCT_PACKAGE_SIZE_ID}")
            return str(package_tag.string)

        except:
            return ""

    def _get_price_descriptor(self) -> str:
        try:
            desc_tag = self._element.find("p", class_=f"chakra-text {DataExtractor.PRICE_DESCRIPTOR_ID}")
            return str(desc_tag.string)

        except:
            return ""

    def _get_price(self) -> dict:
        ''' Return a dictionary of
            prices regarding member price,
           sale price, regular price, depending on
            the data available.'''
        prices = self.data["prices"]
        assert prices["regular_price"] == ""
        assert prices["sale_price"] == ""
        assert prices["mop_price"] == ""
        assert prices["non_member_price"] == ""
        assert prices["before_price"] == ""

        # Start extracting data
        prices = self.data["prices"].copy()

        # Check if regular price is available
        reg_price_tag = self._element.find("span", class_=f"chakra-text {DataExtractor.REGULAR_PRICE_ID}")
        
        if reg_price_tag:
            prices["regular_price"] = str(reg_price_tag.string)

        # Price is nonregular!
        # Attempt to get members only pricing,
        # sale price, before pricing, and non-members pricing.
        else:
            # Member-only price
            mop_tag = self._element.find("p", class_=f"chakra-text {DataExtractor.MOP_REGULAR_PRICE_ID}")
            
            # Non-member price
            nmp_tag = self._element.find("span", class_=f"chakra-text {DataExtractor.NON_MEMBER_PRICE_ID}")

            # Sale price
            sp_tag = self._element.find("span", class_=f"chakra-text {DataExtractor.SALE_PRICE_ID}")

            # Before price
            bfp_tag = self._element.find("span", class_=f"chakra-text {DataExtractor.WAS_PRICE_SALE_ID}")
            
            if mop_tag:
                prices["mop_price"] = str(mop_tag.string)

            if nmp_tag:
                prices["non_member_price"] = str(nmp_tag.string)

            # E.g.:
            # <span class="chakra-text css-o93gbd" data-testid="sale-price">
            #   <span class="css-idkz9h">
            #       sale
            #   </span>
            #   $6.50
            # </span>
            if sp_tag:
                child = sp_tag.span
                assert str(child.string) == "sale"
                prices["sale_price"] = str(child.next_sibling)

            # E.g.:
            # <span class="chakra-text css-623q5h" data-testid="was-price">
            #   <span class="css-idkz9h">
            #       was
            #   </span>
            #   $19.99
            # </span>
            #
            # Note that its possible for no
            # previous price to be available.
            # In that case, leave before_price blank.
            if bfp_tag:
                child = bfp_tag.span
                assert str(child.string) == "was"
                bfp = child.next_sibling

                if bfp:
                    prices["before_price"] = str(bfp.string)

        return prices
