#! /opt/homebrew/bin/python3.11
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
from RealCanadianPageIterator import RealCanadianPageIteratorAsyncDiv
import argparse
import asyncio
import time

FOOD_PAGE_URL = "https://www.realcanadiansuperstore.ca/en/food/c/27985"

if __name__ == "__main__":
    async def production_code():
        # Get the filename and root/seed
        # url from the cmd line.
        parser = argparse.ArgumentParser(description="Basic iterative webscraper for the Real" + \
                                        "Canadian Superstore website")
        parser.add_argument("--uri", "-u", action="store", dest="uri", type=str, required=True)
        parser.add_argument("-s", "--seed", action="store", dest="seed", type=str, default=FOOD_PAGE_URL)
        parser.add_argument("-w", "--workers", action="store", dest="workers", type=int, default=5)
        parser.add_argument("-db", "--database", action="store", dest="database", type=str, required=True)
        parser.add_argument("-col", "--collection", action="store", dest="collection", type=str, required=True)

        # Get the start and end pages (end is inclusive)
        parser.add_argument("-b", "--begin", action="store", dest="begin", type=int)
        parser.add_argument("-e", "--end", action="store", dest="end", type=int)

        # Get the values
        args = parser.parse_args()
        uri = args.uri
        seed = args.seed
        workers = args.workers
        database = args.database
        collection = args.collection
        begin = args.begin
        end = args.end

        # Assert that begin and end are
        # provided together!
        # Formally, check that begin implies end and
        # the converse. (begin <-> end)
        if (begin is None) != (end is None):
            parser.error("Begin and End page must be provided together.")
        
        # Open an asynchronous chromium browser
        async def run_async():
            async with async_playwright() as p:
                pi = RealCanadianPageIteratorAsyncDiv(playwright=p,
                                                browser="chromium",
                                                endpoint_uri=uri,
                                                database=database,
                                                collection=collection,
                                                root_url=seed,
                                                headless=True,
                                                slow_mo=0,
                                                latitude_longitude=(49.8938887, -97.1886292),
                                                permissions=["geolocation"],
                                                store_location=1511)
                await pi.initialize()
                start = time.perf_counter()
                await pi.iterate_pages(workers, begin, end)
                total = time.perf_counter() - start
                print(f"{begin} to {end} iterated in {total}s")

        asyncio.run(run_async())

    # TESTING
    async def run_tests():
        async with async_playwright() as p:
            pi = RealCanadianPageIteratorAsyncDiv(playwright=p,
                                                        browser="chromium",
                                                        endpoint_uri="foo",
                                                        database="foo",
                                                        collection="foo",
                                                        root_url="https://www.realcanadiansuperstore.ca/en/tourti-re/p/21478018_EA?source=nspt",
                                                        headless=False,
                                                        slow_mo=0,
                                                        latitude_longitude=(49.8938887, -97.1886292),
                                                        permissions=["geolocation"],
                                                        store_location=1511)
            await pi.initialize()
            # await pi._test_one_page_with_pagination()
            # await pi._test_one_page_no_pagination()
            # await pi._test_multiple_urls()
            # await pi._test_extract_leafs()
            await pi.crawl()


    asyncio.run(run_tests())
