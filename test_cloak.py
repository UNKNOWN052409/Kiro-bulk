from cloakbrowser import launch
import time

print("Launching CloakBrowser...")
browser = launch(headless=False)
page = browser.new_page()

print("Navigating to ipinfo.io...")
page.goto("https://ipinfo.io/json", wait_until='domcontentloaded', timeout=15000)
time.sleep(2)
body = page.evaluate("() => document.body.innerText")
print(f"IP: {body[:200]}")

print("Checking webdriver status...")
wd = page.evaluate("() => navigator.webdriver")
print(f"navigator.webdriver = {wd}")

print("Checking plugins...")
plugins = page.evaluate("() => navigator.plugins.length")
print(f"navigator.plugins.length = {plugins}")

print("Checking chrome object...")
chrome = page.evaluate("() => typeof window.chrome")
print(f"typeof window.chrome = {chrome}")

browser.close()
print("Done!")
