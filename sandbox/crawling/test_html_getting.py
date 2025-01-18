from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
LINK = "https://www.realcanadiansuperstore.ca/en/food/bakery/c/28002/?navid=flyout-L2-Bakery"
ENDPOINT_URL = "wss://brd-customer-hl_25ccd655-zone-scraping_browser1:pug7nr67kpeo@brd.superproxy.io:9222"

def find_match(pattern: str,
               string: str):
    pattern = re.compile(pattern)
    return pattern.findall(string)

def connect_browser(endpoint_url: str,
                    sync_api: sync_playwright,
                    debug: bool=False):
        ''' Connect to endpoint.
            Returns chromium browser object.'''
        if debug:
            print(f"Connecting to endpoint...")

        browser = sync_api.chromium.connect_over_cdp(endpoint_url)

        if debug:
            print(f"... endpoint connected!")

        return browser

valid_links = []

def get_html(link: str,
              debug: bool=False) -> str:
    ''' Extract the html from the given page.'''
    html = None

    # chakra-text css-1yftjin chakra-text css-1yftjin
    with sync_playwright() as pw:
        # Use proxy browser to connect to page
        browser = connect_browser(ENDPOINT_URL, pw, debug)

        try:
            if debug:
                print(f"Navigating to page...")

            page = browser.new_page()
            page.goto(link)
            html = page.content()

        finally:
            browser.close()

    return html

if __name__ == "__main__":
    with open("test_output.html", "w") as wfile:
        html = get_html(LINK)
        wfile.write(html)
