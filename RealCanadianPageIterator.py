import asyncio
import sys
import os
import json
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from DataExtractor import DataExtractor
from bs4 import BeautifulSoup
from bs4.element import Tag
from MongoClient import MongoClientAsync, CollectionNotFound
from playwright.async_api import async_playwright
from Globals import GROCERY_NAME, HOME_BEAUTY_BABY_NAME, JF_NAME, today
import playwright._impl._errors

class RealCanadianPageIterator(ABC):
    NO_GRID_MESSAGE = "No items are available."
    DEFAULT_FILE_PATH = "leaves/leaves.json"
    DEFAULT_INDENT = 4
    DEFAULT_TIMEOUT_SELECTORS = 30000
    DEFAULT_TIMEOUT_NAVIGATION = 30000
    SITE_DOMAIN = "https://realcanadiansuperstore.ca"

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
        self._playwright = None
        self._root_url = root_url
        self._browser_str = browser
        self._endpoint_uri = endpoint_uri
        self._headless = headless
        self._slow_mo = slow_mo
        self._latitude_longitude = latitude_longitude
        self._permissions = permissions
        self._store_location = store_location

    @abstractmethod
    def scrape(self,
               grocery: bool,
               hbb: bool,
               jf: bool,
               workers: int):
        pass

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
                 store_location: int=None,
                 leafs_filepath: str=RealCanadianPageIterator.DEFAULT_FILE_PATH):

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
        self._db_client = MongoClientAsync(endpoint_uri)
        self._playwright = playwright
        self._leafs_filepath = leafs_filepath


    async def initialize(self):
        self._browser = await getattr(self._playwright, self._browser_str).launch(
            headless=self._headless,
            slow_mo=self._slow_mo
        )
        self._context = await self._create_context(self._browser,
                                            self._latitude_longitude,
                                            self._permissions,
                                            self._store_location)
        
        # Set the timeout for page navigation.
        self._context.set_default_navigation_timeout(self.DEFAULT_TIMEOUT_NAVIGATION)

        # Set the timeout for element selectors
        self._context.set_default_timeout(self.DEFAULT_TIMEOUT_SELECTORS)

    def _modify_url(self,
                url: str,
                page_ind: int):
        if url.endswith("/"):
            url = url[:len(url) - 1]
            
        if page_ind > 1:
            url += f"?page={page_ind}&page={page_ind}"

        return url

    # <------ Helper Functions ------>
    async def _replace_in_db(self,
                           product_dicts: list):
        triplets = []

        # Note that the data extracted from each page
        # does not include barcode data! Include such information.
        for product in product_dicts:
            product["codes"] = {
                "upc": "",
                "ean": "",
                "plu": ""
                }
            triplet = ({"_id": product["product_id"]}, product, True)
            triplets.append(triplet)

        await self._db_client.bulk_replace(triplets)

    async def _insert_in_db(self,
                            product_dicts: list):
        # Note that the data extracted from each page
        # does not include barcode data! Include such information.
        for product in product_dicts:
            product["codes"] = {
                "upc": "",
                "ean": "",
                "plu": ""
                }
            product["_id"] = product["product_id"]

        try:
            await self._db_client.insert_many(product_dicts, ordered=False)

        except:
            pass

    async def _has_product_grid(self, page) -> bool:
        await page.wait_for_load_state("domcontentloaded")
        result_queue = asyncio.Queue()

        async def positive():
            try:
                await page.wait_for_load_state("domcontentloaded")
                await page.query_selector('div[data-testid="product-grid"]')
                await result_queue.put(True)

            except playwright._impl._errors.TimeoutError:
                await result_queue.put(False)

        async def negative():
            try:
                await page.wait_for_load_state("domcontentloaded")
                await page.query_selector("p.css-1na1tkp")
                text = await page.inner_text("p.css-1na1tkp")

                if text == self.NO_GRID_MESSAGE:
                    await result_queue.put(False)

            except playwright._impl._errors.TimeoutError:
                await result_queue.put(True)

        has_no_grid_task = asyncio.create_task(negative())
        has_grid_task = asyncio.create_task(positive())
        result = await result_queue.get()

        if result:
            has_no_grid_task.cancel()
            print(f"{page.url} has a grid!")
        else:
            has_grid_task.cancel()
            print(f"{page.url} has no grid!")

        return result
    async def _extract_product_dicts(self,
                                    page) -> list:
        product_dicts = []

        # Wait for the product grid to be available.
        if await self._has_product_grid(page):
            await page.wait_for_selector('div[data-testid="product-grid"]')
            html = await page.inner_html("div.css-1tjthuk")
            grid_soup = BeautifulSoup(html, "html.parser")
            
            # All the children of the product grid are products!
            for product_div in grid_soup.children:
                product_dicts.append(DataExtractor(product_div).data)

        return product_dicts

    async def _open_page(self,
                         context,
                         origin_page,
                         url: str):
        ''' If an origin page is provided,
        navigate to the url from it.

        If no origin page is provided,
        create a new page from the established context
        and navigate to the url.'''
        assert isinstance(url, str)
        page = origin_page
        
        if not origin_page:
            page = await context.new_page()

        await page.goto(url)
        return page

    async def _navigate_next_page(self,
                        page,
                        curr_page_ind: int,
                        sel_to_wait: str):
        ''' Navigate to page n+1 from page n.'''
        assert isinstance(curr_page_ind, int)
        assert isinstance(sel_to_wait, str)
        await page.wait_for_selector(sel_to_wait)
        next_page_button = page.locator(sel_to_wait)
        await next_page_button.click()

    async def _create_context(self,
                    browser,
                    latitude_longitude: tuple=None,
                    permissions: list=None,
                    store_location: int=None):
        assert isinstance(latitude_longitude, tuple) or latitude_longitude == None
        assert isinstance(permissions, list) or permissions == None
        assert isinstance(store_location, int) or store_location == None
        context = await browser.new_context()

        # Set geolocation if neccessary
        if latitude_longitude:
            assert len(latitude_longitude) == 2
            latitude = latitude_longitude[0]
            longitude = latitude_longitude[1]
            assert isinstance(latitude, float)
            assert isinstance(longitude, float)
            await context.set_geolocation({
                "latitude": latitude,
                "longitude": longitude
            })

        # Set geolocation permissions if needed
        if permissions:
            for permission in permissions:
                assert isinstance(permission, str)

            await context.grant_permissions(permissions)

        # Set the store if needed
        if store_location:
            store_cookie = {
                "name": "last_selected_store",
                "value": f"{store_location}",
                "url": self.SITE_DOMAIN, # TODO: fix hardcoded value
                "httpOnly": False,
                "secure": True,
                "sameSite": "Lax"
            }
            await context.add_cookies([store_cookie])

        return context

class RealCanadianPageIteratorAsyncDiv(RealCanadianPageIteratorAsync):
    async def scrape(self,
                     grocery: bool,
                     hbb: bool,
                     jf: bool,
                     workers: int):
        ''' Scrape every product from every leaf on the website.
        If <grocery>, <hbb>, and <jf> are not provided, utilize the leafs deserialized
        from self._leaf_filepath.

        If <grocery>, <hbb> or <jf> is provided, extract every leaf from the website
        only for the departements passed. After every leaf is extracted,
        scrape every leaf for the products.

        <workers> defines how many pages can be scraping at once.
        This number may be tweaked depending on the local machine's
        tolerance for network traffic.'''
        leafs_dict = None
        
        # Crawl for leaves.
        if grocery or hbb or jf:
            leafs_dict = await self._extract_all_leaves(workers, grocery, hbb, jf)

            # Cache all leaves into the file
            # to make crawling easier in the future.
            if not os.path.exists(self.DEFAULT_FILE_PATH):
                os.makedirs(os.path.dirname(self.DEFAULT_FILE_PATH))

            with open(self._leafs_filepath, "w") as wfile:
                wfile.write(json.dumps(leafs_dict, indent=self.DEFAULT_INDENT))

        # No department was provided.
        # Read from the leaves file.
        else:
            with open(self._leafs_filepath, "r") as rfile:
                leafs_dict = json.load(rfile)

        # Begin scraping and Writing
        # each product to the database.
        await self._scrape_products(leafs_dict, workers)

    # Referenced from Kasravnd in
    # https://stackoverflow.com/questions/30483977/python-get-yesterdays-date-as-a-string-in-yyyy-mm-dd-format
    def _yesterday(self) -> str:
        yesterday = datetime.now() - timedelta(1)
        return yesterday.strftime("%Y-%m-%d")

    async def _migrate_codes(self,
                            db_src: str,
                            col_src: str,
                            db_dest: str,
                            col_dest: str):
        ''' For every product in db_src.col_src with
        any data (UPC, EAN, etc.), migrate those codes to the
        respective item in db_dest.col_dest.'''

        # Verify that the collections exist
        if not await self._db_client.check_exists_col(db_src, col_src):
            raise CollectionNotFound(f"{db_src}.{col_src} doesn't exist!")

        if not await self._db_client.check_exists_col(db_dest, col_dest):
            raise CollectionNotFound(f"{db_dest}.{col_dest} doesn't exist!")

        # Get all documents with code data
        # from the source collection
        self._db_client.select_collection(db_src, col_src)
        code_cursor = await self._db_client.find({
            "codes": {
                "$ne": {
                    "upc": "",
                    "ean": "",
                    "plu": ""
                }
            }
        })
        updates = []

        async for doc in code_cursor:
            updates.append(({"_id": doc["_id"]}, {"$set": {"codes": doc["codes"]}}))

        print(updates)

        # Update all the code data in
        # the destination collection
        # TODO: refactor the client to allow operations without
        # collection selection. Possibility for bugs due to
        # the presence of a global (collection).
        self._db_client.select_collection(db_dest, col_dest)
        if len(updates) != 0:
            result = await self._db_client.bulk_update(updates)
            return result

        return None

    async def _scrape_products(self,
                               leafs_dict: dict,
                               workers: int):
        ''' Scrape data per department and
        migrate all pre-existing code data
        from yesterday to today.'''
        # Start extracting products from every product
        # page (leaf), per department. Write each product to the respective
        # database (the department) and the collection (the current date).
        # For example, A Joe Fresh leaf iterated on Jan 25, 2025 will have documents
        # uploaded to joe-fresh/2025-01-5.
        todays_date = today()
        yesterday = self._yesterday()

        for department in leafs_dict:
            leafs = leafs_dict[department]
            f"Iterating {len(leafs)} leafs for {department}"
            self._db_client.select_collection(database=department, collection=todays_date)
            await self._db_client.create_index("_id")
            counter = 0
            
            for leaf in leafs:
                sys.stdout.write(f"\r[{counter}/{len(leafs)} leafs iterated] {leaf}\n")
                page = await self._open_page(self._context, None, leaf)
                await self._iterate_leaf(page, workers, page_start=1, page_end=None)
                await page.close()
                counter += 1

            try:
                await self._migrate_codes(department, yesterday, department, todays_date)
            
            except CollectionNotFound:
                sys.stderr.write(f"The collection was not found!")

    async def _extract_all_leaves(self,
                                  workers: int,
                                  grocery: bool,
                                  home_beauty_baby: bool,
                                  joe_fresh: bool) -> dict:
        assert isinstance(workers, int)
        assert isinstance(grocery, bool)
        assert isinstance(home_beauty_baby, bool)
        assert isinstance(joe_fresh, bool)
        assert grocery or home_beauty_baby or joe_fresh, "No department was provided!"
        root_page = await self._open_page(self._context, None, self._root_url)
        await root_page.wait_for_selector('nav.primary-nav[aria-label="Main navigation"]')

        # Extract the data from the navigation buttons for only
        # CHABA (home, beauty, baby) and Joe Fresh.
        # Note that the buttons are parents of the span tags.
        # The "ul" tag will be extracted instead of each button
        # to skip needing to emulate hovering on the browser.
        html = await root_page.inner_html('ul.primary-nav__list[data-code="root"]')
        soup = BeautifulSoup(html, "html.parser")

        for child in soup.children:
            if child.button != None:
                if str(child.button.span.string) == "Grocery":
                    grocery_ul_tag = child.ul

                elif str(child.button.span.string) == "Home, Beauty & Baby":
                    hbb_ul_tag = child.ul

                elif str(child.button.span.string) == "Joe Fresh":
                    jf_ul_tag = child.ul

        assert grocery_ul_tag != None, "No Grocery ul tag was extracted." 
        assert hbb_ul_tag != None, "No CHABA ul tag was extracted."
        assert jf_ul_tag != None, "No Joe Fresh ul tag was extracted."

        alert = lambda msg: print(f"#------ {msg} ------#")

        # All relevant department buttons were extracted!
        # Now, extract the urls of all iterable pages (leafs) from these
        # departments and table them in a dictionary.
        leafs_dict = dict()

        # Interestingly, the website stores multiple department products in a
        # single iterable leaf. It contains Deli, Meals-to-Go, Natural Foods,
        # actual Grocery, Meat, and Seafood.
        if grocery:
            alert("Extracting leaf(s) for Grocery...")
            grocery_urls = await self._get_url_surface(grocery_ul_tag)
            alert(f"Extracting leaf(s) for Grocery...")
            grocery_leafs = await self._extract_leafs_department(grocery_urls, workers)
            leafs_dict[GROCERY_NAME] = grocery_leafs

        if home_beauty_baby:
            alert("Extracting category urls for CHABA")
            hbb_urls = await self._get_urls_surface(hbb_ul_tag)
            alert(f"Extracting leaf(s) from CHABA...")
            hbb_leafs = await self._extract_leafs_department(hbb_urls, workers)
            leafs_dict[HOME_BEAUTY_BABY_NAME] = hbb_leafs

        if joe_fresh:
            alert("Extracting category urls for Joe Fresh")
            jf_urls = await self._get_urls_surface(jf_ul_tag)
            alert(f"Extracting leaf(s) for Joe Fresh...")
            jf_leafs = await self._extract_leafs_department(jf_urls, workers)
            leafs_dict[JF_NAME] = jf_leafs

        return leafs_dict

    # ------ Extraction of each department ------ #
    async def _get_urls_surface(self, department_tag) -> list:
        '''For the given <department>, extract all level-1 urls.'''
        links = []

        for li_tag in department_tag.contents:
            assert li_tag.name == "li"
            links.append(self.SITE_DOMAIN + li_tag.a.get("href"))

        return links

    async def _extract_leafs_department(self, department_links: list, workers: int):
        async def foo(leafs_mutable: list, link: str):
            print(f"Extracting links from {link}")
            page = await self._open_page(self._context, None, link)
            leafs = await self._extract_leafs(page)
            print(f"{len(leafs)} leafs extracted from {link}")
            await page.close()
            leafs_mutable.extend(leafs)
            
        leafs = []
        num_links_start = len(department_links)
        curr_link_id = 1

        while len(department_links) != 0:
            tasks = []

            for _ in range(workers):
                if len(department_links) > 0:
                    curr_link = department_links.pop()
                    
                    # TODO: remove debugging hardcoded link
                    if curr_link != "https://realcanadiansuperstore.ca/en/collection/jf-seasonal-shops?navid=flyout-L2-jf-seasonal-shops":
                        print(f"[{curr_link_id}/{num_links_start}] Extracting leafs from {curr_link}")
                        tasks.append(foo(leafs, curr_link))
                        curr_link_id += 1

            await asyncio.gather(*tasks)
        return leafs

    async def _extract_leafs(self, page) -> list:
        assert page != None

        # Base case: the current page is a leaf
        if await self._is_leaf(page):
            return [page.url]
        
        try:
            # Observe the side accordion list of the page, like in
            # https://www.realcanadiansuperstore.ca/en/baby/c/27987?navid=flyout-L2-Baby.
            # Extract the links of every category.
            await page.wait_for_selector("div.chakra-accordion.css-8atqhb")
            accordion_list_html = await page.inner_html("div.chakra-accordion.css-8atqhb")
            accordion_soup = BeautifulSoup(accordion_list_html, "html.parser")
            links = []

        except playwright._impl._errors.TimeoutError:
            # The current page is special, like
            # https://www.realcanadiansuperstore.ca/en/collections/joe-fresh-lunar-new-year.
            # For now, we will ignore pages like these, as the leaf pages
            # are special too (the product tags are distinct).
            return []
        
        for div in accordion_soup.children:
            assert div.get("class")[0] == "css-srrvm8", breakpoint()
            pulled_list = div.find("ul", class_="css-pc4dq5")
            see_all_tag = pulled_list.contents[0]
            assert see_all_tag.string == "See All"
            link_tag = see_all_tag.find("a", class_="css-1o1i5mr")
            links.append("https://www.realcanadiansuperstore.ca" + str(link_tag.get("href"))) # TODO: fix harcoded domain string.

        # Exhaust every path until every
        # leaf is found.
        leafs = []

        # Begin recursion for each link
        for link in links:
            new_page = await self._open_page(self._context, None, link)

            for leaf in await self._extract_leafs(new_page):
                leafs.append(leaf)
                
            # Save memory by closing tab
            await new_page.close()
        return leafs
 
    async def _is_leaf(self, page) -> bool:
        # If the page contains this element, it must be a leaf:
        # <hr aria-orientation="horizontal" class="chakra-divider css-1ap8ayt">
        await page.wait_for_load_state("domcontentloaded")
        result_queue = asyncio.Queue()

        async def positive():
            try:
                await page.wait_for_selector("hr.css-1ap8ayt")
                await result_queue.put(True)

            except playwright._impl._errors.TimeoutError:
                await result_queue.put(False)
        
        async def negative():
            try:
                # await page.wait_for_selector("div.chakra-accordion.css-8atqhb")
                await page.wait_for_selector("div.indiana-scroll-container")
                await result_queue.put(False)

            except playwright._impl._errors.TimeoutError:
                await result_queue.put(True)

        is_leaf_task = asyncio.create_task(positive())
        not_leaf_task = asyncio.create_task(negative())
        result = await result_queue.get()
        
        if result:
            not_leaf_task.cancel()

        else:
            is_leaf_task.cancel()
        return result

    async def _get_last_page(self, page) -> int | None:
        ''' Return the last iterable page from the
        current page.'''

        try:
            # Wait for the page navigation to be available
            # at the bottom of the page.
            # await page.wait_for_selector("nav.css-1rb8z0p")
            await page.wait_for_selector("nav.css-1rb8z0p")
            html = await page.inner_html("nav.css-1rb8z0p")
            pagination_soup = BeautifulSoup(html, "html.parser")

            # Narrow all selected elements to
            # the indexed page buttons. Ignore the navigation arrow
            # and ellipsis.
            indexed_page_buttons = pagination_soup.find_all("a", class_="chakra-link css-1vwc5vj")

            # Observe the last button's index:
            # it is the last available page.
            # Note the strange syntax below: .string returns
            # <class 'bs4.element.NavigableString'>. It must be converted to a genuine
            # string before converted to an integer.
            return int(str(indexed_page_buttons[-1].string))

        except playwright._impl._errors.TimeoutError:
            # No locator was loaded on the page!
            # Assume that no pagination exists
            return None

    #------- Leaf iteration code --------------#
    async def _iterate_leaf(self,
                            page,
                            workers: int,
                            page_start: int,
                            page_end: int | None):
        ''' Allow <workers> many tabs to be open
        and allow each to iterate pages in their respective
        intervals.

        If there are more workers than pages,
        let # workers == # pages.'''
        assert isinstance(workers, int)
        assert isinstance(page_start, int)
        assert isinstance(page_end, int) or page_end == None
        assert workers >= 1

        # Check whether an indefinite iteration
        # is to happen.
        if page_end == None:
            last_page_id = await self._get_last_page(page)

            # There was no pagination element at
            # the bottom of the page!
            if not last_page_id:
                page_end = 1

            else:
                page_end = last_page_id
            
        # Check whether there are enough pages
        # to distribute among the workers.
        assert page_end != None
        num_pages = (page_end - page_start) + 1

        if num_pages <= workers:
            workers = num_pages

        # Start distributing page intervals across the workers.
        pages_per_interval = int(num_pages / workers)
        pages_remainder = num_pages % workers

        # Define the page intervals for each worker.
        # A basic linear equation is used for each interval:
        # let n = page_start
        # let L = (page_end - page_start) + 1
        # let Ii = (xi, yi), where L = |xi - yi| for all i
        # Then, xi = n + (i-1)*L
        # and yi = xi + L - 1
        intervals = []

        for i in range(1, workers + 1):
            xi = page_start + (i-1) * pages_per_interval
            yi = xi + pages_per_interval - 1
            
            # The last worker will iterate the
            # remaining pages (division was uneven).
            if i == workers and pages_remainder != 0:
                yi += pages_remainder

            intervals.append((xi, yi))

        # Define our processing for each page.
        # For any given page, extract all the products
        # and write to our database.
        async def extract_write(page):
            try:
                products = await self._extract_product_dicts(page)
        
                if len(products) != 0:
                    # await self._replace_in_db(products)
                    await self._insert_in_db(products)

            # TODO: remove this and debug which pages get timeouterrors
            except playwright._impl._errors.TimeoutError:
                sys.stderr.write(f"Error at {page.url}\n")

        # Get coroutines to gather.
        # DEBUGGING CODE
        async def debug_wrapper(num_pages_iterated,
                                page,
                                page_start,
                                page_end,
                                page_callback):
            num_pages = page_end - page_start + 1
            sys.stdout.write(f"\r{num_pages_iterated[0]}/{num_pages} pages iterated\n")

            if num_pages_iterated[0] == num_pages:
                sys.stdout.write("\n")

            await self._iterate_leaf_one(page=page,
                                        page_start = page_start, page_end = page_end,
                                        page_callback = page_callback)
            num_pages_iterated[0] += 1

        iterate_tasks = [debug_wrapper(num_pages_iterated=[0],
                                        page=await self._open_page(self._context, None, self._modify_url(page.url, intervals[i][0])),
                                        page_start=intervals[i][0],
                                        page_end=intervals[i][1],
                                        page_callback=extract_write)
            for i in range(len(intervals))]

        await asyncio.gather(*(iterate_tasks))

    async def _iterate_leaf_one(self,
                                page,
                                page_start: int,
                                page_end: int,
                                page_callback):
            assert isinstance(page_start, int)
            assert isinstance(page_end, int)
            assert page_start <= page_end
            assert page_start > 0

            # Start iterating from page_start to page_end inclusive
            i = page_start
            
            # For each page, extract the product json
            # and write it to the database.
            while i <= page_end:
                await page_callback(page)
                # print(f"[PAGE {i}] extracted from {page.url}")
                # DEBUGGING CODE
                if i > 1:
                    assert page.url.split("=")[-1] == str(i)

                if i != page_end:
                    await self._navigate_next_page(page, i, '[aria-label="Next Page"]')

                i += 1
            await page.close()

    # passed
    async def _test_one_page_with_pagination(self):
        TEST_URL = "https://www.realcanadiansuperstore.ca/en/food/c/27985"
        page = await self._open_page(self._context, None, TEST_URL)
        last_page = await self._get_last_page(page)
        assert last_page == 209

    # passed!
    async def _test_one_page_no_pagination(self):
        TEST_URL = "https://www.realcanadiansuperstore.ca/en/batteries-automotive/automotive-electronics/c/28097"
        page = await self._open_page(self._context, None, TEST_URL)
        last_page = await self._get_last_page(page)
        assert last_page == None

    # passed!
    async def _test_multiple_urls(self):
        urls = ["https://www.realcanadiansuperstore.ca/en/pet-food-supplies/dogs/c/28040",
                "https://www.realcanadiansuperstore.ca/en/pet-food-supplies/cats/c/28039",
                "https://www.realcanadiansuperstore.ca/en/pet-food-supplies/small-animals/c/28043",
                "https://www.realcanadiansuperstore.ca/en/pet-food-supplies/birds/c/28038"]

        async def test_driver(url: str):
            page = await self._open_page(self._context, None, url)
            last_page = await self._get_last_page(page)
            print(f"[{last_page}]: {url}")

        tasks = [test_driver(url) for url in urls]
        await asyncio.gather(*tasks)

    async def _test_leafs(self):
        page = await self._open_page(self._context, None, "https://www.google.com/")

        async def assert_leaf(link: str):
            page = await self._open_page(self._context, None, link)
            assert await self._is_leaf(page), f"FAIL: {link} is not a leaf."
            print(f"PASSED: {link} is a leaf.")
            await page.close()

        async def assert_not_leaf(link: str):
            page = await self._open_page(self._context, None, link)
            assert not await self._is_leaf(page), f"FAIL: {link} is a leaf."
            print(f"PASSED: {link} isn't a leaf.")
            await page.close()
            
        async def assert_leafs(urls):
            for url in urls:
                await assert_leaf(url)

        async def assert_not_leafs(urls):
            for url in urls:
                await assert_not_leaf(url)

        async def baby():
            print("\nTesting baby...")

            async def is_leaf():
                print("Verifying leaves...")
                urls = [
                    "https://www.realcanadiansuperstore.ca/en/baby/diapers-wipes-training-pants/c/28030",
                    "https://www.realcanadiansuperstore.ca/en/baby/nursing-feeding-accessories/c/28031",
                    "https://www.realcanadiansuperstore.ca/en/baby/pregnancy-maternity/c/28035",
                    "https://www.realcanadiansuperstore.ca/en/baby/baby-toiletries/c/28025",
                    "https://www.realcanadiansuperstore.ca/en/baby/baby-toys/c/28028",
                    "https://www.realcanadiansuperstore.ca/en/baby/gear/c/28032",
                    "https://www.realcanadiansuperstore.ca/en/baby/baby-safety/c/28026",
                    "https://www.realcanadiansuperstore.ca/en/baby/car-seats-strollers/c/28029",
                    "https://www.realcanadiansuperstore.ca/en/baby/gifts/c/28033",
                    "https://www.realcanadiansuperstore.ca/en/baby/nursery/c/28034",
                    "https://www.realcanadiansuperstore.ca/en/baby/baby-food-snacks/cereal/c/46860",
                    "https://www.realcanadiansuperstore.ca/en/baby/baby-food-snacks/jars/c/30938",
                    "https://www.realcanadiansuperstore.ca/en/baby/baby-food-snacks/pouches/c/30939",
                    "https://www.realcanadiansuperstore.ca/en/baby/baby-food-snacks/snacks-biscuits/c/30946",
                    "https://www.realcanadiansuperstore.ca/en/baby/baby-food-snacks/toddler-food/c/30947"
                ]
                await assert_leafs(urls)

            async def not_leaf():
                print("Verifying non-leafs...")
                urls = [
                    "https://www.realcanadiansuperstore.ca/en/baby/baby-food-snacks/c/42410"
                ]
                await assert_not_leafs(urls)
            await is_leaf()
            await not_leaf()

        async def joe_fresh():
            print(f"\nTesting joe fresh...")

            async def is_leaf():
                print(f"Verifying leafs...")
                urls = [
                    "https://www.realcanadiansuperstore.ca/en/joe-fresh/women/c/56018?navid=flyout-L2-joe-fresh-women&navid=flyout-L2-jf-womens",
                    "https://www.realcanadiansuperstore.ca/en/joe-fresh/men/c/56216?navid=flyout-L2-joe-fresh-men",
                    "https://www.realcanadiansuperstore.ca/en/joe-fresh/girls/c/56343?navid=flyout-L2-joe-fresh-girls",
                    "https://www.realcanadiansuperstore.ca/en/joe-fresh/boys/c/56482?navid=flyout-L2-joe-fresh-boys",
                    "https://www.realcanadiansuperstore.ca/en/joe-fresh/toddlers/girls/c/56573?navid=flyout-L2-joe-fresh-toddlers",
                    "https://www.realcanadiansuperstore.ca/en/joe-fresh/toddlers/boys/c/56574?navid=flyout-L2-Toddler%20Boy",
                    "https://www.realcanadiansuperstore.ca/en/joe-fresh/baby/c/56770?navid=flyout-L2-joe-fresh-baby"
                ]
                await assert_leafs(urls)

            async def not_leaf():
                print(f"Verifying non-leafs...")
                urls = [
                    "https://www.realcanadiansuperstore.ca/en/collection/jf-seasonal-shops?navid=flyout-L2-jf-seasonal-shops"
                ]
                await assert_not_leafs(urls)
            await is_leaf()
            await not_leaf()

        async def grocery():
            print(f"\nTesting grocery...")

            async def is_leaf():
                print(f"Testing leafs...")
                urls = [
                    "https://www.realcanadiansuperstore.ca/en/food/meat/sausages/c/28170",
                    "https://www.realcanadiansuperstore.ca/en/food/meat/sausages/fresh-sausages/c/56935",
                    "https://www.realcanadiansuperstore.ca/en/floral-shop/c/58821?navid=flyout-L2-FloralShop"
                ]
                await assert_leafs(urls)

            async def not_leaf():
                print(f"Testing non-leafs...")
                urls = [
                    "https://www.realcanadiansuperstore.ca/en/food/fruits-vegetables/c/28000?navid=flyout-L2-fruits-vegetables",
                    "https://www.realcanadiansuperstore.ca/en/food/dairy-eggs/c/28003?navid=flyout-L2-Dairy-and-Eggs",
                    "https://www.realcanadiansuperstore.ca/en/food/meat/c/27998?navid=flyout-L2-Meat",
                    "https://www.realcanadiansuperstore.ca/en/food/pantry/c/28006?navid=flyout-L2-Pantry",
                    "https://www.realcanadiansuperstore.ca/en/food/international-foods/c/58044?navid=flyout-L2-International-Foods",
                    "https://www.realcanadiansuperstore.ca/en/food/snacks-chips-candy/c/57025?navid=flyout-L2-snacks-chips-and-candy",
                    "https://www.realcanadiansuperstore.ca/en/food/frozen-food/c/28005?navid=flyout-L2-frozen-food",
                    "https://www.realcanadiansuperstore.ca/en/food/natural-and-organic/c/28189?navid=flyout-L2-Natural-Organic",
                    "https://www.realcanadiansuperstore.ca/en/food/bakery/c/28002?navid=flyout-L2-Bakery",
                    "https://www.realcanadiansuperstore.ca/en/food/prepared-meals/c/27996?navid=flyout-L2-Prepared-Meals",
                    "https://www.realcanadiansuperstore.ca/en/food/drinks/c/28004?navid=flyout-L2-Drinks",
                    "https://www.realcanadiansuperstore.ca/en/food/deli/c/28001?navid=flyout-L2-Deli",
                    "https://www.realcanadiansuperstore.ca/en/food/fish-seafood/c/27999?navid=flyout-L2-Fish-and-Seafood",
                ]
                await assert_not_leafs(urls)
            await is_leaf()
            await not_leaf()

        async def no_items():
            print(f"\nTesting no items...")

            async def is_leaf():
                print(f"Testing leafs...")
                urls = [
                    "https://www.realcanadiansuperstore.ca/en/lawn-garden-patio/garden-centre/c/28012?navid=flyout-L3-Floral-Garden",
                    "https://www.realcanadiansuperstore.ca/en/lawn-garden-patio/insect-pest-control/c/28140?navid=CLP-L3-Insect-and-Pest-Control&navid=flyout-L3-Insect-Pest%20Control",
                    "https://www.realcanadiansuperstore.ca/en/lawn-garden-patio/patio-accessories/c/57036",
                    "https://www.realcanadiansuperstore.ca/en/lawn-garden-patio/garden-centre/c/28012?navid=flyout-L3-Floral-Garden",
                ]
                await assert_leafs(urls)
            await is_leaf()
        await baby()
        await joe_fresh()
        await grocery()
        await no_items()
                    
    async def _test_extract_leafs(self):
        async def no_click():
            async def international():
                url = "https://www.realcanadiansuperstore.ca/en/food/international-foods/c/58044?navid=flyout-L2-International-Foods"
                page = await self._open_page(self._context, None, url)
                leafs = await self._extract_leafs(page)
                print(leafs)

            async def baby():
                url = "https://www.realcanadiansuperstore.ca/en/baby/c/27987?navid=flyout-L2-Baby"
                page = await self._open_page(self._context, None, url)
                leafs = await self._extract_leafs(page)
                print(leafs)

            await international()
            await baby()
        await no_click()

    async def _test_extract_all_leafs(self):
        async def extract_grocery():
            gr_dict = await self._extract_all_leaves(4, True, False, False)
            breakpoint()

        async def extract_hbb():
            hbb_dict = await self._extract_all_leaves(4, False, True, False)
            breakpoint()

        async def extract_jf():
            jf_dict = await self._extract_all_leaves(4, False, False, True)
            breakpoint()

        async def extract_all():
            leafs_dict = await self._extract_all_leaves(4, True, True, True)
            breakpoint()

        # await extract_grocery()
        # await extract_hbb()
        # await extract_jf()
        await extract_all()

    async def _test_extract_products(self):
        self._db_client.select_collection(database="test_db", collection="test_collection")

        async def driver(urls: list, num_workers: int):
            for url in urls:
                print(f"Iterating {url}...")
                page = await self._open_page(self._context, None, url)
                await self._iterate_leaf(page, num_workers, page_start=1, page_end=None)

        urls = [
            "https://www.realcanadiansuperstore.ca/en/food/fruits-vegetables/fresh-fruits/c/28194",
            "https://www.realcanadiansuperstore.ca/en/food/fruits-vegetables/packaged-salad-dressing/c/28196",
            "https://www.realcanadiansuperstore.ca/en/food/fruits-vegetables/in-store-salads/c/59222",
            "https://www.realcanadiansuperstore.ca/en/food/fruits-vegetables/herbs/c/28197",
            "https://www.realcanadiansuperstore.ca/en/baby/baby-food-snacks/cereal/c/46860",
            "https://www.realcanadiansuperstore.ca/en/food/dairy-eggs/butter-spreads/c/28220",
            "https://www.realcanadiansuperstore.ca/en/personal-care-beauty/oral-care/c/59770"
        ]
        # Iterate through each leaf with 1 - 4 workers.
        for i in range(1, 4 + 1):
            print(f"Testing with {i} worker(s).")
            await driver(urls, i)

        async def workers_lt_pages():
            urls = [
                "https://www.realcanadiansuperstore.ca/en/joe-fresh/women/c/56018?navid=flyout-L2-joe-fresh-women&navid=flyout-L2-jf-womens",
                "https://www.realcanadiansuperstore.ca/en/food/c/27985"
            ]
            await driver(urls, 2)

        async def workers_eq_pages():
            urls = [
                "https://www.realcanadiansuperstore.ca/en/joe-fresh/baby/c/56770?navid=flyout-L2-joe-fresh-baby",
                "https://www.realcanadiansuperstore.ca/en/joe-fresh/girls/c/56343?navid=flyout-L2-joe-fresh-girls",
                "https://www.realcanadiansuperstore.ca/en/food/fruits-vegetables/fresh-fruits/c/28194"

            ]
            await driver(urls, 4)

        async def workers_gt_pages():
            urls = [
                "https://www.realcanadiansuperstore.ca/en/joe-fresh/boys/c/56482?navid=flyout-L2-joe-fresh-boys"
            ]
            await driver(urls, 4)
        print("Testing workers < pages...")
        await workers_lt_pages()

        # Passed!
        print("Testing workers == pages...")
        await workers_eq_pages()

        # Passed!
        print("Testing workers > pages...")
        await workers_gt_pages()

    async def _test_connection_db(self):
        print("Connecting...")
        print(self._db_client.select_collection(database="test_db", collection="test_collection"))
        print(f"Connected.")
        print("Writing POC...")
        await self._db_client.insert_one({"write": "success"})
        print("POC written!")

    async def _test_code_migration(self):
        print("Testing code migration!")
        result = await self._migrate_codes("test_src", "col_src", "test_dest", "col_dest")
        print(f"Result is {result}")
