import json
import logging
import os
import re
import sys
from pathlib import Path
from time import sleep
from typing import Callable, Dict, Tuple

import undetected_chromedriver as uc
from dotenv import load_dotenv
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

log = logging.getLogger()
log.setLevel("INFO")
handler = logging.StreamHandler(sys.stdout)
handler.setLevel("INFO")
formatter = logging.Formatter(
    "[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s",
    "%Y-%m-%d %H:%M:%S",
)
handler.setFormatter(formatter)
log.addHandler(handler)

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "https://anchira.to")
BROWSER_DATA_DIR = os.getenv("BROWSER_DATA_DIR")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TIMEOUT = int(os.getenv("TIMEOUT", 10))

download_dir = Path.cwd() / "downloaded"
cookies_txt = Path.cwd() / "cookies.txt"
favorited_json = Path.cwd() / "favorited.json"
downloaded_json = Path.cwd() / "downloaded.json"

with cookies_txt.open("r") as f:
    cookies_str = f.read()
    cookie_dicts = [
        {
            "name": cookie.split("=")[0],
            "value": cookie.split("=")[1],
        }
        for cookie in cookies_str.split("; ")
    ]

with favorited_json.open("r", encoding="utf-8") as f:
    favorited_data: Dict[str, str] = json.load(f)


def program_exit():
    log.warning("Program exit.")
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


def get_url(url):
    log.debug(f"fetching url: {url}")
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


def wait_for_condition(condition: Callable):
    elm_found = False
    while not elm_found:
        try:
            elm_found = WebDriverWait(browser, TIMEOUT).until(condition)
        except TimeoutException as err:
            log.info(err)


def do_while_wait_for_condition(fn: Callable, condition: Callable):
    elm_found = False
    while not elm_found:
        try:
            fn()
            elm_found = WebDriverWait(browser, 1).until(condition)
        except TimeoutException as err:
            log.info(err)


def set_cookies(browser: uc.Chrome):
    get_url(BASE_URL)
    wait_for_condition(
        expected_conditions.presence_of_element_located((By.CSS_SELECTOR, "#main"))
    )
    for cookie_dict in cookie_dicts:
        browser.add_cookie(cookie_dict)


set_cookies(browser)


def text_not_empty_in_element(locator: Tuple[str, str]):
    """An expectation for checking if the given text is not empty
    specified element.

    locator, text
    """

    def _predicate(driver):
        try:
            element_text = driver.find_element(*locator).text
            return element_text
        except StaleElementReferenceException:
            return False

    return _predicate


def write_to_downloaded_json(url: str, filename: str):
    with downloaded_json.open("r+", encoding="utf-8") as f:
        downloaded_data: Dict[str, str] = json.load(f)
        if url not in downloaded_data.keys():
            downloaded_data[url] = filename
            downloaded_data = dict(
                sorted(downloaded_data.items(), key=lambda item: item[1])
            )
            f.seek(0)
            json.dump(obj=downloaded_data, fp=f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.truncate()


ARCHIVE_NAME_SELECTOR = "#gallery #metadata > header > span.s"
DOWNLOAD_BTN_SELECTOR = "#gallery #actions > button[title='Download']"
ORIGINAL_BTN_SELECTOR = "#modal #downloads > button[title='Original']"
DOWNLOADER_FILENAME_SELECTOR = "#downloader > main > article > header > button > h3"
DOWNLOADER_EMPTY_SELECTOR = "#downloader main:not(:has(article))"


def download_archive(url):
    get_url(url)
    wait_for_condition(
        text_not_empty_in_element((By.CSS_SELECTOR, ARCHIVE_NAME_SELECTOR))
    )
    wait_for_condition(
        expected_conditions.presence_of_element_located(
            (By.CSS_SELECTOR, DOWNLOAD_BTN_SELECTOR)
        )
    )
    download_btn = browser.find_element(By.CSS_SELECTOR, DOWNLOAD_BTN_SELECTOR)
    download_btn.click()

    wait_for_condition(
        expected_conditions.visibility_of_element_located(
            (By.CSS_SELECTOR, ORIGINAL_BTN_SELECTOR)
        )
    )
    original_btn = browser.find_element(By.CSS_SELECTOR, ORIGINAL_BTN_SELECTOR)
    do_while_wait_for_condition(
        lambda: original_btn.click(),
        expected_conditions.invisibility_of_element(
            (By.CSS_SELECTOR, ORIGINAL_BTN_SELECTOR)
        ),
    )
    wait_for_condition(
        expected_conditions.presence_of_element_located(
            (By.CSS_SELECTOR, DOWNLOADER_FILENAME_SELECTOR)
        )
    )
    archive_filename = (
        browser.find_element(By.CSS_SELECTOR, DOWNLOADER_FILENAME_SELECTOR)
        .text.replace(":", "_")
        .replace("?", "_")
    )

    write_to_downloaded_json(url, archive_filename)
    wait_for_condition(
        expected_conditions.presence_of_element_located(
            (By.CSS_SELECTOR, DOWNLOADER_EMPTY_SELECTOR)
        )
    )


def download_all_favorites():
    for url, path in favorited_data.items():
        with downloaded_json.open("r", encoding="utf-8") as f:
            downloaded_data: Dict[str, str] = json.load(f)
        if not url in downloaded_data.keys():
            log.info(f"downloading favorite: {url}:{path}")
            download_archive(url)


def clean_download_index():
    downloaded_archives = set(archive.stem for archive in download_dir.iterdir())
    with downloaded_json.open("r+", encoding="utf-8") as f:
        downloaded_data: Dict[str, str] = json.load(f)
        downloaded_archives_index = set(downloaded_data.values())
        extra_archives_str = "\n".join(downloaded_archives_index - downloaded_archives)
        if extra_archives_str:
            log.warning(
                f"difference between actually downloaded and indexed downloaded: \n{extra_archives_str}"
            )
        downloaded_data = {
            url: archive_filename
            for url, archive_filename in downloaded_data.items()
            if archive_filename in downloaded_archives
        }
        downloaded_data = dict(
            sorted(downloaded_data.items(), key=lambda item: item[1])
        )
        f.seek(0)
        json.dump(obj=downloaded_data, fp=f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.truncate()


clean_download_index()
download_all_favorites()
