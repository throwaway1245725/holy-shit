import json
import re
import time
from pathlib import Path
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

URL_PATTERN = re.compile(r"https:\/\/ksk\.moe\/view\/(.*)")
N_RESULTS_PATTERN = re.compile(r"Found (.*) result")
FAVORITE_STATUS_INDICATOR = "unfavorite"

index_json = Path.cwd() / "index.json"
favorited_json = Path.cwd() / "favorited_ksk.json"
cookies_txt = Path.cwd() / "cookies.txt"

with cookies_txt.open("r") as f:
    cookies = f.read()

with index_json.open("r", encoding="utf-8") as f:
    index_data: Dict[str, Dict[str, str]] = json.load(f)

entries = (
    (artist, entry, url)
    for artist, entries in index_data.items()
    for entry, url in entries.items()
)


def add_missing_favorites():
    for artist, entry, url in entries:
        with favorited_json.open("r+", encoding="utf-8") as f:
            favorited_data: Dict[str, str] = json.load(f)
            if url in favorited_data.keys():
                # print(f"not adding {artist}/{entry} already in favorites")
                pass
            else:
                print(f"adding {artist}/{entry} to favorites")
                partial_url = URL_PATTERN.match(url).group(1)
                response = requests.post(
                    f"https://ksk.moe/favorite/{partial_url}",
                    headers={"cookie": cookies},
                )
                if response.status_code != 200:
                    raise Exception("what!?")
                favorited_data[url] = f"{artist}/{entry}"
                # sorting by value
                favorited_data = dict(
                    sorted(favorited_data.items(), key=lambda item: item[1])
                )
                f.seek(0)
                json.dump(obj=favorited_data, fp=f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.truncate()


def find_weirdness():
    for artist, entries in index_data.items():
        page = requests.get(
            f'https://ksk.moe/favorites?s=artist:"{artist}"',
            headers={"cookie": cookies},
        )
        soup = BeautifulSoup(page.text, "html.parser")
        n_results_str = soup.find(id="galleries").header.i.text
        n_results = int(
            N_RESULTS_PATTERN.match(n_results_str).group(1).replace(",", "")
        )
        if n_results != len(entries):
            print(
                f"artist {artist} number of entries mismatch ({n_results} vs {len(entries)})"
            )


def count_total_favorites():
    with favorited_json.open("r", encoding="utf-8") as f:
        favorited_data: Dict[str, str] = json.load(f)
    urls = set(favorited_data.keys())
    print(f"number of entries in total: {len(urls)}")


def check_favorite_urls():
    with favorited_json.open("r", encoding="utf-8") as f:
        favorited_data: Dict[str, str] = json.load(f)
    for url, name in favorited_data.items():
        print(f"checking {name}")
        check_favorite_url(url)


def check_favorite_url(url):
    page = requests.get(url, headers={"cookie": cookies})
    soup = BeautifulSoup(page.text, "html.parser")
    favorite_status = (
        soup.find(id="actions").find("button", class_="favorite").span.text
    ).lower()
    if favorite_status != FAVORITE_STATUS_INDICATOR:
        print(f"favorite status mismatch: {url}")


add_missing_favorites()
count_total_favorites()
# check_favorite_urls()
# find_weirdness()
