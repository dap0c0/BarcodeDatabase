import asyncio
import time
import sys
from abc import ABC, abstractmethod
from DataExtractor import DataExtractor
from bs4 import BeautifulSoup
from bs4.element import Tag
from MongoClient import MongoClientAsync
import playwright._impl._errors

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
        self._playwright = playwright
        self._root_url = root_url
        self._browser_str = browser
        self._endpoint_uri = endpoint_uri
        self._headless = headless
        self._slow_mo = slow_mo
        self._latitude_longitude = latitude_longitude
        self._permissions = permissions
        self._store_location = store_location

    @abstractmethod
    def crawl(self, workers: int):
        pass

    @abstractmethod
    async def _iterate_leaf(self,
                            page,
                            workers: int,
                            page_start: int,
                            page_end: int):
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
        self._db_client = MongoClientAsync(endpoint_uri)

    async def initialize(self):
        self._browser = await getattr(self._playwright, self._browser_str).launch(
            headless=self._headless,
            slow_mo=self._slow_mo
        )
        self._context = await self._create_context(self._browser,
                                            self._latitude_longitude,
                                            self._permissions,
                                            self._store_location)

    def _modify_url(self,
                url: str,
                page_ind: int):
        if url.endswith("/"):
            url = url[:len(url) - 1]
            
        url += f"?page={page_ind}"

        return url

    # <------ Helper Functions ------>
    async def _write_to_db(self,
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

    async def _extract_product_dicts(self,
                                    page) -> list:
        # Wait for the product grid to be available.
        await page.wait_for_selector('div[data-testid="product-grid"]')
        html = await page.inner_html("div.css-1tjthuk")
        grid_soup = BeautifulSoup(html, "html.parser")
        
        # All the children of the product grid are products!
        product_dicts = []

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
                "url": "https://www.realcanadiansuperstore.ca", # TODO: fix hardcoded value
                "httpOnly": False,
                "secure": True,
                "sameSite": "Lax"
            }
            await context.add_cookies([store_cookie])

        return context

class RealCanadianPageIteratorAsyncDiv(RealCanadianPageIteratorAsync):
    # TODO: fix hardcoded values for desired departments to crawl.
    async def crawl(self, workers: int):
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
                if str(child.button.span.string) == "Home, Beauty & Baby":
                    hbb_ul_tag = child.ul

                elif str(child.button.span.string) == "Joe Fresh":
                    jf_ul_tag = child.ul
        
        assert hbb_ul_tag != None, "No CHABA ul tag was extracted."
        assert jf_ul_tag != None, "No Joe Fresh ul tag was extracted."

        # All relevant department buttons were extracted!
        # Now, extract the url of all iterable pages (leafs) from these
        # departments and iterate each and every one of them.
        hbb_urls = await self._get_urls_surface(hbb_ul_tag)
        print(f"Got category urls for CHABA")

        jf_urls = await self._get_urls_surface(jf_ul_tag)
        print("Got category urls for Joe Fresh")

        print("Extracting leafs...")
        print(f"Extracting leafs from CHABA...")
        hbb_leafs = await self._extract_leafs_department(hbb_urls, workers)

        print(f"Extracting leafs from Joe Fresh...")
        jf_leafs = await self._extract_leafs_department(jf_urls, workers)

        # Start extracting products from every product
        # page (leaf), per department. Write each product to the respective
        # database (the department) and the collection (the current date).
        # For example, A Joe Fresh leaf iterated on Jan 25, 2025 will have documents
        # uploaded to joe-fresh/2025-01-5.
        date = time.strftime("%Y-%m-%d")
        leafs_list = [
            ("grocery", ["https://www.realcanadiansuperstore.ca/en/food/c/27985"]),
            ("home-beauty-baby", hbb_leafs),
            ("joe-fresh", jf_leafs)
        ]
        for pair in leafs_list:
            department, leafs = pair
            self._db_client.select_collection(database=department, collection=date)
            await self._db_client.create_index("_id")
            page = await self._open_page(self._context, None, "https://www.google.com")
            
            for leaf in leafs:
                page = await self._open_page(self._context, page, leaf)
                await self._iterate_leaf(page, workers, page_start=1, page_end=None)

    # ------ Extraction of each department ------ #
    async def _get_urls_surface(self, department_tag) -> list:
        '''For the given <department>, extract all level-1 urls.'''
        links = []

        for li_tag in department_tag.contents:
            assert li_tag.name == "li"
            links.append("https://realcanadiansuperstore.ca" + li_tag.a.get("href"))

        return links

    async def _extract_leafs_department(self, department_links: list, workers: int):
        async def foo(leafs_mutable: list, link: str):
            print(f"Extracting links from {link}")
            page = await self._open_page(self._context, None, link)
            leafs = await self._extract_leafs(page)
            print(f"{len(leafs)} leafs extracted from {link}")
            await page.close()
            leafs_mutable.append(leafs)
            
        leafs = []

        while len(department_links) != 0:
            tasks = []

            for _ in range(workers):
                tasks.append(await foo(leafs, department_links.pop()))

            await asyncio.gather(*tasks)
        return leafs

    async def _extract_leafs(self, page) -> list:
        assert page != None

        # Base case: the current page is a leaf
        if await self._is_leaf(page):
            return [page.url]
        
        # Observe the side accordion list of the page, like in
        # https://www.realcanadiansuperstore.ca/en/baby/c/27987?navid=flyout-L2-Baby.
        # Extract the links of every category.
        await page.wait_for_selector("div.chakra-accordion.css-8atqhb")
        accordion_list_html = await page.inner_html("div.chakra-accordion.css-8atqhb")
        accordion_soup = BeautifulSoup(accordion_list_html, "html.parser")
        links = []
        
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
            await page.wait_for_srelector("nav.css-1rb8z0p")
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
            if yi == workers:
                yi += pages_remainder

            intervals.append((xi, yi))

        # Define our processing for each page.
        # For any given page, extract all the products
        # and write to our database.
        async def extract_write(page):
            products = await self._extract_product_dicts(page)
            await self._write_to_db(products)

        # Get coroutines to gather.
        iterate_tasks = [self._iterate_leaf_one(page, intervals[i][0], intervals[i][1], extract_write)
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
                print(f"Extracted {page.url}")

                if i != page_end:
                    await self._navigate_next_page(page, i, '[aria-label="Next Page"]')

                i += 1
            await page.close()

    # passed!
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


