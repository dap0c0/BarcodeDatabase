#! /opt/homebrew/bin/python3.11
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
from RealCanadianPageIterator import RealCanadianPageIteratorSync, RealCanadianPageIteratorAsync
import argparse
import asyncio
import time

FOOD_PAGE_URL = "https://www.realcanadiansuperstore.ca/en/food/c/27985"

if __name__ == "__main__":
    # Get the filename and root/seed
    # url from the cmd line.
    parser = argparse.ArgumentParser(description="Basic iterative webscraper for the Real" + \
                                     "Canadian Superstore website")
    parser.add_argument("--uri", "-u", action="store", dest="uri", type=str, required=True)
    parser.add_argument("-s", "--seed", action="store", dest="seed", type=str, default=FOOD_PAGE_URL)
    parser.add_argument("-w", "--workers", action="store", dest="workers", type=int, default=5)

    # Get the start and end pages (end is inclusive)
    parser.add_argument("-b", "--begin", action="store", dest="begin", type=int)
    parser.add_argument("-e", "--end", action="store", dest="end", type=int)

    # Get the values
    args = parser.parse_args()
    uri = args.uri
    seed = args.seed
    workers = args.workers
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
            pi = RealCanadianPageIteratorAsync(playwright=p,
                                            browser="chromium",
                                            endpoint_uri=uri,
                                            database="page_data",
                                            collection="jan_9",
                                            root_url=seed,
                                            headless=False,
                                            slow_mo=0,
                                            latitude_longitude=(49.8938887, -97.1886292),
                                            permissions=["geolocation"],
                                            store_location=1511)
            await pi.initialize()
            start = time.perf_counter()
            await pi.iterate_pages_div(workers, begin, end)
            total = time.perf_counter() - start
            print(f"{begin} to {end} iterated in {total}s")

    asyncio.run(run_async())
