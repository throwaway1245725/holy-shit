import json
import re
from pathlib import Path
from time import sleep
from typing import Dict

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions

from browser_setup import (
    CAPTCHA,
    browser,
    do_while_wait_for_condition,
    get_url,
    text_not_empty_in_element,
    wait_for_condition,
)
from log_setup import log

download_dir = Path.cwd() / "downloaded"
favorited_json = Path.cwd() / "favorited.json"
downloaded_json = Path.cwd() / "downloaded.json"

with favorited_json.open("r", encoding="utf-8") as f:
    favorited_data: Dict[str, str] = json.load(f)


def download_archive(url):
    ARCHIVE_NAME_SELECTOR = "#gallery #metadata > header > span.s"
    DOWNLOAD_BTN_SELECTOR = "#gallery #actions > button[title='Download']"
    ORIGINAL_BTN_SELECTOR = "#modal #downloads > button[title='Original']"
    CAPTCHA_IFRAME_COMPLETED_SELECTOR = (
        "#h-captcha iframe:not([data-hcaptcha-response=''])"
    )
    CAPTCHA_SUBMIT_SELECTOR = "#h-captcha + button"
    DOWNLOADER_EMPTY_SELECTOR = "#downloader main:not(:has(article))"

    get_url(url)
    wait_for_condition(
        text_not_empty_in_element((By.CSS_SELECTOR, ARCHIVE_NAME_SELECTOR)),
        "ARCHIVE_NAME_SELECTOR",
    )
    download_btn: WebElement = wait_for_condition(
        expected_conditions.presence_of_element_located(
            (By.CSS_SELECTOR, DOWNLOAD_BTN_SELECTOR)
        ),
        "DOWNLOAD_BTN_SELECTOR",
    )
    download_btn.click()

    original_btn: WebElement = wait_for_condition(
        expected_conditions.visibility_of_element_located(
            (By.CSS_SELECTOR, ORIGINAL_BTN_SELECTOR)
        ),
    )
    do_while_wait_for_condition(
        lambda: original_btn.click(),
        expected_conditions.invisibility_of_element(
            (By.CSS_SELECTOR, ORIGINAL_BTN_SELECTOR)
        ),
        "ORIGINAL_BTN_SELECTOR",
    )
    if CAPTCHA:
        wait_for_condition(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, CAPTCHA_IFRAME_COMPLETED_SELECTOR)
            )
        )
        captcha_submit_btn: WebElement = wait_for_condition(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, CAPTCHA_SUBMIT_SELECTOR)
            )
        )
        captcha_submit_btn.click()

    wait_for_condition(
        expected_conditions.presence_of_element_located(
            (By.CSS_SELECTOR, DOWNLOADER_EMPTY_SELECTOR)
        ),
        "DOWNLOADER_EMPTY_SELECTOR",
    )
    get_downloaded_filename(url)
    sleep(1)


def get_downloaded_filename(url):
    DUPLICATE_FILE_PATTERN = re.compile(r"^(.*) \(\d\)$")

    original_window = browser.current_window_handle
    browser.switch_to.new_window("tab")
    get_url("chrome://downloads")
    wait_for_condition(
        expected_conditions.presence_of_element_located(
            (By.CSS_SELECTOR, "downloads-manager")
        )
    )
    filename: str = browser.execute_script(
        "return document.querySelector('downloads-manager').shadowRoot.querySelector('#downloadsList downloads-item').shadowRoot.querySelector('div#content  #file-link').text"
    )

    archive_filename = download_dir / filename.replace(":", "_").replace("?", "_")
    if (m := DUPLICATE_FILE_PATTERN.match(archive_filename.stem)) and (
        download_dir / f"{m.group(1)}{archive_filename.suffix}"
    ).exists():
        log.warning(f"{archive_filename} is a duplicate, ignoring")
        browser.execute_script(
            "document.querySelector('downloads-manager').shadowRoot.querySelector('#downloadsList downloads-item').shadowRoot.querySelector('div#content  #safe.controls cr-button[focus-type=\"cancel\"]')?.click()"
        )
    else:
        write_to_downloaded_json(url, archive_filename.stem)
    browser.close()
    browser.switch_to.window(original_window)


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


def download_all_favorites():
    for url, path in favorited_data.items():
        with downloaded_json.open("r", encoding="utf-8") as f:
            downloaded_data: Dict[str, str] = json.load(f)
        if not url in downloaded_data.keys():
            log.warning(f"downloading favorite: '{url} : {path}'")
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
