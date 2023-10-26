import json
import logging
import os
import re
from pathlib import Path
from time import sleep
from typing import Dict

import undetected_chromedriver as uc
from dotenv import load_dotenv
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

log = logging.getLogger()
load_dotenv()

BASE_URL = os.getenv("BASE_URL", "https://anchira.to")
BROWSER_DATA_DIR = os.getenv("BROWSER_DATA_DIR")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TIMEOUT = int(os.getenv("TIMEOUT", 10))

cookies_txt = Path.cwd() / "cookies.txt"
favorited2_json = Path.cwd() / "favorited2.json"

with cookies_txt.open("r") as f:
    cookies_str = f.read()
    cookie_dicts = [
        {
            "name": cookie.split("=")[0],
            "value": cookie.split("=")[1],
        }
        for cookie in cookies_str.split("; ")
    ]


def program_exit():
    log.info("Program exit.")
    if browser:
        browser.quit()
    exit()


def init_browser():
    options = uc.ChromeOptions()
    options.add_argument("--disable-web-security")
    new_browser = uc.Chrome(
        user_data_dir=BROWSER_DATA_DIR,
        headless=HEADLESS,
        options=options,
        patcher_force_close=True,
        enable_cdp_events=True,
    )
    new_browser.set_script_timeout(TIMEOUT)
    new_browser.set_page_load_timeout(TIMEOUT)
    return new_browser


browser = init_browser()


def waiting_loading_page(url, css_selector="#main"):
    log.info(f"Loading url: {url}")
    tried = 0
    timeout = TIMEOUT
    while True:
        try:
            browser.get(url)
            break
        except TimeoutException as err:
            log.info("Error: timed out waiting for page to load.")
            if tried > 3:
                log.info(err.msg)
                log.info(f"Connection timeout: {url}")
                program_exit()
            tried += 1
            timeout *= 1.5
            browser.set_script_timeout(timeout)
            browser.set_page_load_timeout(timeout)
            sleep(0.1)

    elm_found = False
    while not elm_found:
        try:
            element = expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, css_selector)
            )
            elm_found = WebDriverWait(browser, TIMEOUT).until(element)
        except TimeoutException as err:
            print(err)


def set_cookies(browser: uc.Chrome):
    waiting_loading_page(BASE_URL)
    for cookie_dict in cookie_dicts:
        browser.add_cookie(cookie_dict)


set_cookies(browser)

FAVORITE_ARTICLE_SELECTOR = "#main > #feed > main > article"


def parse_favorite_page(page):
    waiting_loading_page(
        BASE_URL + f"/favorites?page={page}", FAVORITE_ARTICLE_SELECTOR
    )
    articles = browser.find_elements(By.CSS_SELECTOR, FAVORITE_ARTICLE_SELECTOR)
    with favorited2_json.open("r+", encoding="utf-8") as f:
        favorited_data: Dict[str, str] = json.load(f)
        for article in articles:
            a = article.find_element(By.TAG_NAME, "a")
            link = a.get_attribute("href")
            artists = article.find_elements(
                By.CSS_SELECTOR, 'div a[data-namespace="1"]'
            )
            if link and link not in favorited_data.keys():
                favorited_data[link] = (
                    f"{artists[0].accessible_name}/{a.accessible_name}"
                    if artists
                    else f"unknown/{a.accessible_name}"
                )

        favorited_data = dict(sorted(favorited_data.items(), key=lambda item: item[1]))
        f.seek(0)
        json.dump(obj=favorited_data, fp=f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.truncate()


PAGE_PATTERN = re.compile(r".*\/favorites\?page=(\d+)")


def get_favorites():
    waiting_loading_page(BASE_URL + "/favorites", FAVORITE_ARTICLE_SELECTOR)
    last_page_btn = browser.find_element(
        By.CSS_SELECTOR, '#main > #feed > footer > nav > a[title*="last page"'
    )
    last_page_link = last_page_btn.get_attribute("href")
    if (
        not last_page_link
        or not (m := PAGE_PATTERN.match(last_page_link))
        or not m.group(1)
    ):
        raise Exception("can't find last page button")
    n_pages: str = m.group(1)

    for page in range(1, int(n_pages) + 1):
        log.info(f"parsing page: {page}")
        parse_favorite_page(page)


get_favorites()
