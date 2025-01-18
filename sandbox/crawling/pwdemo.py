from playwright.sync_api import sync_playwright

# Open page via chromium synchronously
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=100)
    page = browser.new_page()
    page.goto('https://google.com')

