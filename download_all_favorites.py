import json
import logging
from pathlib import Path
from time import sleep
from typing import Dict, Union

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions

from browser_setup import (
    do_while_wait_for_condition,
    get_url,
    text_not_empty_in_element,
    wait_for_condition,
    wait_for_condition_once,
)
from log_setup import log

download_dir = Path.cwd() / "downloaded"
favorited_json = Path.cwd() / "favorited.json"
downloaded_json = Path.cwd() / "downloaded.json"

with favorited_json.open("r", encoding="utf-8") as f:
    favorited_data: Dict[str, str] = json.load(f)


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


def download_archive(url):
    ARCHIVE_NAME_SELECTOR = "#gallery #metadata > header > span.s"
    DOWNLOAD_BTN_SELECTOR = "#gallery #actions > button[title='Download']"
    ORIGINAL_BTN_SELECTOR = "#modal #downloads > button[title='Original']"
    DOWNLOADER_FILENAME_SELECTOR = "#downloader > main > article > header > button > h3"
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
    filename_el: Union[WebElement, None] = wait_for_condition_once(
        expected_conditions.presence_of_element_located(
            (By.CSS_SELECTOR, DOWNLOADER_FILENAME_SELECTOR)
        ),
        "DOWNLOADER_FILENAME_SELECTOR",
    )
    if filename_el:
        archive_filename = filename_el.text.replace(":", "_").replace("?", "_")
        write_to_downloaded_json(url, archive_filename)
    wait_for_condition(
        expected_conditions.presence_of_element_located(
            (By.CSS_SELECTOR, DOWNLOADER_EMPTY_SELECTOR)
        ),
        "DOWNLOADER_EMPTY_SELECTOR",
    )
    sleep(2)


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
