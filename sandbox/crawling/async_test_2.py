import asyncio
from playwright.async_api import async_playwright, Playwright
PAGE_A = "https://www.realcanadiansuperstore.ca/en/food/c/27985"
PAGE_B = "https://www.realcanadiansuperstore.ca/en/cilantro/p/20091825001_EA?source=nspt"
PAGE_C = "https://www.realcanadiansuperstore.ca/en/pub-style-chicken-strips-fully-cooked/p/21191828_EA?source=nspt"
# Open the food page and two other ones

async def open_page(browser, url):
    page = await browser.new_page()
    await page.goto(url)
    print(f"Paga {url} opened!")

async def run(playwright: Playwright):
    # Open chromium browser
    chromium = playwright.chromium
    browser = await chromium.launch(headless=True)

    # Open all three pages
    # asynchronously.
    tasks = [open_page(browser, PAGE_A),
             open_page(browser, PAGE_B),
             open_page(browser, PAGE_C)]

    await asyncio.gather(*tasks)

async def main():
    async with async_playwright() as playwright:
        await run(playwright)

asyncio.run(main())

