import json
import os
from pathlib import Path
from typing import Dict

import requests
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv

from log_setup import log

load_dotenv()

HN_BASE_URL = os.getenv("HN_BASE_URL", "")
IGNORE_ALREADY_PROCESSED = (
    os.getenv("IGNORE_ALREADY_PROCESSED", "true").lower() == "true"
)

favorited_json = Path.cwd() / "favorited.json"

cookies_txt = Path.cwd() / "hn_cookies.txt"
with cookies_txt.open("r") as f:
    cookies_str = f.read()
    cookies_dict = {
        cookie.split("=")[0]: cookie.split("=")[1] for cookie in cookies_str.split("; ")
    }


def get_url(url: str) -> requests.Response:
    return requests.get(url, cookies=cookies_dict)


def get_artist(url: str) -> str:
    page = get_url(url)
    soup = BeautifulSoup(page.text, "html.parser")
    artist_el = soup.select("table.view-page-details a[href^='/?q=artist:']", limit=1)[
        0
    ]
    return artist_el.find(text=True, recursive=False).strip()  # type: ignore


def parse_favorite_page(page_num: int) -> bool:
    FAVORITE_CARD_SELECTOR = "a[href^='/view/'] > .card"
    page = get_url(f"{HN_BASE_URL}/favorites/page/{page_num}")
    soup = BeautifulSoup(page.text, "html.parser")
    with favorited_json.open("r+", encoding="utf-8") as f:
        favorited_data: Dict[str, str] = json.load(f)
        reached_already_processed = False
        for entry in soup.select(FAVORITE_CARD_SELECTOR):
            link: str = f"{HN_BASE_URL}{entry.parent['href']}"  # type: ignore
            title: str = entry.header.p.text  # type: ignore
            if link not in favorited_data.keys():
                artist = get_artist(link)
                favorited_data[link] = f"!<not yet downloaded> [{artist}] {title}"
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
    LAST_PAGE_SELECTOR = "ul.pagination-list li:last-child"
    page = get_url(f"{HN_BASE_URL}/favorites")
    soup = BeautifulSoup(page.text, "html.parser")
    last_page_num: str = soup.select(LAST_PAGE_SELECTOR, limit=1)[0].a.text  # type: ignore
    for page_num in range(1, int(last_page_num) + 1):
        log.info(f"parsing page: {page_num}")
        reached_already_processed = parse_favorite_page(page_num)
        if reached_already_processed:
            log.info("reached already processed, stopping")
            break


get_favorites()
