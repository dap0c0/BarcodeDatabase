import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# Get the last page by:
#   - opening a web browser (playwright)
#   - navigating to the page
#   - waiting until the selector is available
#   - extract all of the following elements:
#       - <a class="chakra-link" css-1vwc5vj></a>
#
#   - The very last element extracted in the list
#   is the last page available to iterate
TEST_URL = "https://www.realcanadiansuperstore.ca/en/food/c/27985"

async def main():
    async with async_playwright() as playwright:
        # Launch browser
        browser = await playwright.chromium.launch(headless=False, slow_mo=10)

        # Navigate to the page
        page = await browser.new_page()
        await page.goto(TEST_URL, wait_until="domcontentloaded")

        # Wait till the page navigation boxes
        # are available.
        await page.wait_for_selector("a.chakra-link.css-1vwc5vj")

        # Get the html in this particular area
        html = await page.inner_html('nav[aria-label="Pagination"].css-1rb8z0p')
        
        # Extract all pagination html!
        soup = BeautifulSoup(html, "html.parser")

        # From the pagination html, only extract
        # the numbered buttons.
        indexed_button_elements = soup.find_all("a", class_="chakra-link css-1vwc5vj")
        return int(indexed_button_elements[-1])

    

asyncio.run(main())
