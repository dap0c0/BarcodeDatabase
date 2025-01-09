import os.path
from abc import ABC, abstractmethod
from playwright.sync_api import sync_playwright
from DataExtractor import DataExtractor
from bs4 import BeautifulSoup
from bs4.element import Tag
from MongoClient import MongoClientSync
import json

class RealCanadianPageIterator(ABC):
    def __init__(self,
                    playwright,
                    browser: str,
                    endpoint_uri: str,
                    root_url: str,
                    headless: bool=False,
                    slow_mo: int=100,
                    latitude_longitude: tuple=None,
                    permissions: list=None,
                    store_location: int=None):
            assert isinstance(browser, str)
            assert isinstance(endpoint_uri, str)
            assert isinstance(root_url, str)
            assert isinstance(headless, bool)
            assert isinstance(slow_mo, int)
            assert isinstance(latitude_longitude, tuple)
            assert isinstance(permissions, list)
            assert isinstance(store_location, int)

            # Dynamically create the browser
            self._browser = getattr(playwright, browser).launch(
                headless=headless,
                slow_mo=slow_mo
            )
            self._context = self._create_context(self._browser,
                                                latitude_longitude,
                                                permissions,
                                                store_location)
            self._root_url = root_url

    @abstractmethod
    def iterate_pages(self,
                       page_start: int,
                       page_end: int):
        pass

    # <------ Helper Functions ------>
    def _extract_product_dicts(self,
                              page) -> list:
        # Wait until the following are visible:
        # <div id="root">
        #   <div id="site-layout">
        #       <div class="site-layout__content">
        #           <main class="site-content" id="site-content">
        #               <div class="view-resolver-component">
        #                   <div class="css-1nntebs">
        #                       <div class="css-0">
        #                           <div class="css-1tjthuk">
        #
        # id -> #
        # class -> .
        page.is_visible("div#root")
        page.is_visible("div#site-layout")
        page.is_visible("div.site-layout__content")
        page.is_visible("div.view-resolver-component")
        page.is_visible("div.css-1nntebs")
        page.is_visible("div.css-0")

        # Wait for the product grid to be available.
        page.wait_for_selector('div[data-testid="product-grid"]')
        html = page.inner_html("div.css-1tjthuk")
        grid_soup = BeautifulSoup(html, "html.parser")
        
        # All the children of the product grid are products!
        product_dicts = []

        for product_div in grid_soup.children:
            product_dicts.append(DataExtractor(product_div).data)

        return product_dicts

    def _create_context(self,
                    browser,
                    latitude_longitude: tuple=None,
                    permissions: list=None,
                    store_location: int=None):
        assert isinstance(latitude_longitude, tuple) or latitude_longitude == None
        assert isinstance(permissions, list) or permissions == None
        assert isinstance(store_location, int) or store_location == None
        context = browser.new_context()

        # Set geolocation if neccessary
        if latitude_longitude:
            assert len(latitude_longitude) == 2
            latitude = latitude_longitude[0]
            longitude = latitude_longitude[1]
            assert isinstance(latitude, float)
            assert isinstance(longitude, float)
            context.set_geolocation({
                "latitude": latitude,
                "longitude": longitude
            })

        # Set geolocation permissions if needed
        if permissions:
            for permission in permissions:
                assert isinstance(permission, str)

            context.grant_permissions(permissions)

        # Set the store if needed
        if store_location:
            store_cookie = {
                "name": "last_selected_store",
                "value": f"{store_location}",
                "url": "https://www.realcanadiansuperstore.ca", # TODO: fix hardcoded value
                "httpOnly": False,
                "secure": True,
                "sameSite": "Lax"
            }
            context.add_cookies([store_cookie])

        return context

    def _navigate_next_page(self,
                        page,
                        curr_page_ind: int,
                        page_end_ind: int,
                        sel_to_wait: str):
        ''' Navigate to page n+1 from page n.'''
        assert isinstance(curr_page_ind, int)
        assert isinstance(page_end_ind, int)
        assert isinstance(sel_to_wait, str)
        page.wait_for_selector(sel_to_wait)
        next_page_button = page.locator(sel_to_wait)
        next_page_button.click()


class RealCanadianPageIteratorSync(RealCanadianPageIterator):
    def __init__(self,
                playwright,
                browser: str,
                database: str,
                collection: str,
                 
                endpoint_uri: str,
                root_url: str,
                headless: bool=False,
                slow_mo: int=100,
                latitude_longitude: tuple=None,
                permissions: list=None,
                store_location: int=None):
        RealCanadianPageIterator.__init__(self,
                                        playwright,
                                        browser,
                                        endpoint_uri,
                                        root_url,
                                        headless,
                                        slow_mo,
                                        latitude_longitude,
                                        permissions,
                                        store_location)

        # Allow the data to be written
        # to the server.
        self._db_client = MongoClientSync(endpoint_uri)
        self._db_client.select_collection(database, collection)
           
    def iterate_pages(self,
                      page_start,
                      page_end):
        ''' Iterate pages from page_start to page_end inclusive.
        For each page, extract dictionaries of data and write
        into self._item_database.'''

        def replace_many(page):
            dicts = self._extract_product_dicts(page)
            triplets = []

            # Note that the data extracted from each page
            # does not include barcode data! Include such information.
            for product in dicts:
                product["codes"] = {
                    "upc": "",
                    "ean": "",
                    "plu": ""
                    }
                triplet = ({"_id": product["product_id"]}, product, True)
                triplets.append(triplet)

            self._db_client.bulk_replace(triplets)

        self._db_client.create_index("_id")
        self._iterate_pages(self._context,
                            page_start,
                            page_end,
                            replace_many)

    def _iterate_pages(self,
                    context,
                    page_start: int,
                    page_end: int,
                    page_callback,
                    wait_condition: str="domcontentloaded"):
        ''' From <page_start> to <page_end> inclusive,
            iterate through the pages exhaustively,
            calling <page_callback> for each page.'''
        assert isinstance(page_start, int)
        assert isinstance(page_end, int)
        assert isinstance(wait_condition, str)
        assert page_start <= page_end
        assert page_start > 0
        
        # First navigate to the start page_start
        curr_url = self._root_url
        
        if page_start != 1:
            curr_url += f"?page={page_start}"

        page = context.new_page()
        page.goto(curr_url, wait_until=wait_condition)

        # Start iterating until page_end is hit.
        i = page_start

        while i <= page_end:
            page_callback(page)

            if i != page_end:
                self._navigate_next_page(page,
                                    i,
                                    page_end,
                                    '[aria-label="Next Page"]')
            i += 1

class RealCanadianPageIteratorAsync(RealCanadianPageIterator):
    def __init__(self,
                 playwright,
                 browser: str,
                 endpoint_uri: str,
                 root_url: str,
                 headless: bool=False,
                 slow_mo: int=100,
                 latitude_longitude: tuple=None,
                 permissions: list=None,
                 store_location: int=None):

        RealCanadianPageIterator.__init__(self,
                                        playwright,
                                        browser,
                                        endpoint_uri,
                                        root_url,
                                        headless,
                                        slow_mo,
                                        latitude_longitude,
                                        permissions,
                                        store_location)
