#! /opt/homebrew/bin/python3.11
from playwright.sync_api import sync_playwright
from RealCanadianPageIterator import RealCanadianPageIterator
import argparse

FOOD_PAGE_URL = "https://www.realcanadiansuperstore.ca/en/food/c/27985/"

if __name__ == "__main__":
    # Get the filename and root/seed
    # url from the cmd line.
    parser = argparse.ArgumentParser(description="Basic iterative webscraper for the Real" + \
                                     "Canadian Superstore website")
    parser.add_argument("-f", "--file", action="store", dest="file", required=True, type=str)
    parser.add_argument("-s", "--seed", action="store", dest="seed", type=str, default=FOOD_PAGE_URL)

    # Get the start and end pages (end is inclusive)
    parser.add_argument("-b", "--begin", action="store", dest="begin", type=int)
    parser.add_argument("-e", "--end", action="store", dest="end", type=int)

    # Get the values
    args = parser.parse_args()
    file = args.file
    seed = args.seed
    begin = args.begin
    end = args.end

    # Assert that begin and end are
    # provided together!
    # Formally, check that begin implies end and
    # the converse. (begin <-> end)
    if (begin is None) != (end is None): # Check whether 
        parser.error("Begin and End page must be provided together.")
    
    # Open a synchronous chromium browser
    with sync_playwright() as p:
        pi = RealCanadianPageIterator(playwright=p,
                                      filepath=file,
                                      browser="chromium",
                                      root_url=seed,
                                      headless=False,
                                      slow_mo=100,
                                      latitude_longitude=(49.8938887, -97.1886292),
                                      permissions=["geolocation"],
                                      store_location=1511)
        pi.iterate_pages(begin, end)
