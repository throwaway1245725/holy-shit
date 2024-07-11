import json
import os
from pathlib import Path
from time import sleep
from typing import Any, Callable, Union

from ..monkey_patches import patch_undetected_chromedriver

patch_undetected_chromedriver()

import undetected_chromedriver as uc
from dotenv import load_dotenv
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from ..log_setup import log

load_dotenv(Path(__file__).parent.parent / ".env")

K_BASE_URL = os.getenv("K_BASE_URL")
BROWSER_DATA_DIR = os.getenv("BROWSER_DATA_DIR")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TIMEOUT = int(os.getenv("TIMEOUT", 10))
CAPTCHA = os.getenv("CAPTCHA", "false").lower() == "true"
if CAPTCHA:
    HEADLESS = False

cookies_txt = Path(__file__).parent / "k_cookies.txt"
localstorage_json = Path(__file__).parent / "k_localstorage.json"

with cookies_txt.open("r") as f:
    cookies_str = f.read()
    cookie_dicts = [
        {
            "name": cookie.split("=")[0],
            "value": cookie.split("=")[1],
        }
        for cookie in cookies_str.split("; ")
    ]

with localstorage_json.open("r") as f:
    localstorage_dict: dict[str, str] = json.load(f)


def program_exit():
    log.warning("Program exit.")
    if browser:
        browser.quit()
    exit()


def init_browser():
    options = uc.ChromeOptions()
    # options.add_argument("--disable-web-security")
    new_browser = uc.Chrome(
        user_data_dir=BROWSER_DATA_DIR,
        headless=HEADLESS,
        options=options,
        patcher_force_close=True,
        enable_cdp_events=True,
        version_main=125,
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


def wait_for_condition(
    condition: Callable[[expected_conditions.WebDriverOrWebElement], Any], selector=""
) -> Any:
    elm_found = None
    while not elm_found:
        try:
            elm_found = WebDriverWait(browser, TIMEOUT).until(condition)
        except TimeoutException as err:
            log.warning(f"timeout while wait_for_condition: {selector}")
            log.debug(err)
    return elm_found


def wait_for_condition_once(
    condition: Callable[[expected_conditions.WebDriverOrWebElement], Any], selector=""
) -> Union[Any, None]:
    try:
        return WebDriverWait(browser, TIMEOUT).until(condition)
    except TimeoutException:
        log.warning(f"timeout while wait_for_condition_once: {selector}")
        return


def do_while_wait_for_condition(
    fn: Callable[[], None],
    condition: Callable[[expected_conditions.WebDriverOrWebElement], Any],
    selector="",
) -> Any:
    elm_found = None
    while not elm_found:
        try:
            fn()
            elm_found = WebDriverWait(browser, 1).until(condition)
        except TimeoutException as err:
            log.warning(f"timeout while do_while_wait_for_condition: {selector}")
            log.debug(err)
    return elm_found


def set_cookies_and_localstorage(browser: uc.Chrome):
    get_url(K_BASE_URL)
    wait_for_condition(
        expected_conditions.presence_of_element_located((By.CSS_SELECTOR, "#main")),
        "#main",
    )
    browser.execute_script("window.localStorage.setItem('filter','[]');")
    for item, value in localstorage_dict.items():
        browser.execute_script(f"window.localStorage.setItem('{item}', '{value}')")

    for cookie_dict in cookie_dicts:
        browser.add_cookie(cookie_dict)


set_cookies_and_localstorage(browser)


def text_not_empty_in_element(locator: tuple[str, str]):
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
