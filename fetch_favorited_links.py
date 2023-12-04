import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions

from browser_setup import BASE_URL, get_url, wait_for_condition
from log_setup import log

load_dotenv()

IGNORE_ALREADY_PROCESSED = (
    os.getenv("IGNORE_ALREADY_PROCESSED", "true").lower() == "true"
)

favorited_json = Path.cwd() / "favorited.json"


def parse_favorite_page(page: int) -> bool:
    FAVORITE_ARTICLE_SELECTOR = "#main > .feed > main > article"
    get_url(f"{BASE_URL}/favorites?page={page}")
    articles: List[WebElement] = wait_for_condition(
        expected_conditions.presence_of_all_elements_located(
            (By.CSS_SELECTOR, FAVORITE_ARTICLE_SELECTOR)
        ),
        "FAVORITE_ARTICLE_SELECTOR",
    )
    with favorited_json.open("r+", encoding="utf-8") as f:
        favorited_data: Dict[str, str] = json.load(f)
        reached_already_processed = False
        for article in articles:
            a = article.find_element(By.TAG_NAME, "a")
            link = a.get_attribute("href")
            artists = article.find_elements(
                By.CSS_SELECTOR, 'div a[data-namespace="1"]'
            )
            if link:
                if link not in favorited_data.keys():
                    favorited_data[link] = (
                        f"!<not yet downloaded> {artists[0].accessible_name}/{a.accessible_name}"
                        if artists
                        else f"!<not yet downloaded> unknown/{a.accessible_name}"
                    )
                else:
                    reached_already_processed = True
                    break

        favorited_data = dict(sorted(favorited_data.items(), key=lambda item: item[1]))
        f.seek(0)
        json.dump(obj=favorited_data, fp=f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.truncate()
        return reached_already_processed


def get_favorites():
    PAGE_PATTERN = re.compile(r".*\/favorites\?page=(\d+)")
    LAST_PAGE_SELECTOR = "#main > .feed > footer > nav > a[title*='last page']"
    get_url(f"{BASE_URL}/favorites")
    last_page_btn: WebElement = wait_for_condition(
        expected_conditions.presence_of_element_located(
            (By.CSS_SELECTOR, LAST_PAGE_SELECTOR)
        ),
        "LAST_PAGE_SELECTOR",
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
        reached_already_processed = parse_favorite_page(page)
        if reached_already_processed:
            log.info("reached already processed, stopping")
            break


get_favorites()
