# pyright: reportOptionalMemberAccess=false
# pyright: reportOptionalSubscript=false
import json
import math
import operator
import os
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from functools import reduce
from io import BytesIO
from itertools import islice
from pathlib import Path
from typing import Dict, Union
from urllib.parse import urljoin, urlparse

import pytz
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageChops
from slugify import slugify

from log_setup import log

F_BASE_URL = os.getenv("F_BASE_URL", "")
I_BASE_URL = os.getenv("I_BASE_URL", "")
F_MULTI_KEYS_MAPPING = {
    "Artist": "artists",
    "Parody": "parodies",
    "Circle": "circles",
    "Event": "events",
    "Magazine": "magazines",
    "Publisher": "publishers",
}
ANCHIRA_SEQ_PATTERN = re.compile(r".*\/g\/(\d+)\/.*")
PAGES_PATTERN = re.compile(r".*?(\d+) pages?.*")
THUMBNAIL_PAGE_PATTERN = re.compile(r".*\/thumbs\/(\d+)\.thumb.*")
IMAGE_SUFFIXES = [".jpg", ".jpeg", ".png"]


data_dir = Path.cwd() / "data"

downloaded_json = Path.cwd() / "downloaded.json"
with downloaded_json.open(mode="r", encoding="utf-8") as f:
    downloaded_data: Dict[str, str] = json.load(f)

index_json = Path.cwd() / "index.json"
with index_json.open(mode="r", encoding="utf-8") as f:
    index_data: Dict[str, Dict[str, str]] = json.load(f)

original_sources_json = Path.cwd() / "original_sources.json"
with original_sources_json.open(mode="r", encoding="utf-8") as f:
    original_sources_data: Dict[str, str] = json.load(f)

cookies_txt = Path.cwd() / "f_cookies.txt"
with cookies_txt.open("r") as f:
    cookies_str = f.read()
    cookies_dict = {
        cookie.split("=")[0]: cookie.split("=")[1] for cookie in cookies_str.split("; ")
    }

headers_dict = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}


def do_slugify(s: str) -> str:
    s = re.sub("’", "'", s)
    s = re.sub("？", "", s)
    s = re.sub("–", "-", s)
    s = re.sub("&amp;", "-", s)
    return slugify(
        s,
        replacements=[
            ["'", ""],
            ["❤", ""],
            ["☆", ""],
            ["&", ""],
            ["♀", ""],
            ["_", ""],
            [".", ""],
            [":", "-"],
            ["꞉", "-"],
            ["*", ""],
            ["犬", ""],
        ],
    )


def clean_directory_name(name: str):
    ARTIST_NAME_PATTERN = r"^\[[^\]]*\]"
    TAGS_PATTERN = r"\{[^\}]*\}$"
    KOUSHOKU_PATTERN = r"\(koushoku\.org\)|\(ksk\.moe\)"
    EXTRA_INFO_PATTERN = r"(?:\([^\)]*\)|\[[^\]]*\])(?:\s(?:\[.*\])*)*$"
    new_name = re.sub(ARTIST_NAME_PATTERN, "", name)
    new_name = re.sub(TAGS_PATTERN, "", new_name)
    new_name = re.sub(KOUSHOKU_PATTERN, "", new_name)
    new_name = re.sub("’", "'", new_name)
    new_name = re.sub("？", "", new_name)
    new_name = re.sub("–", "-", new_name)
    new_name = re.sub(EXTRA_INFO_PATTERN, "", new_name)
    return new_name.strip()


def get_url(url: str) -> requests.Response:
    return requests.get(url, cookies=cookies_dict, headers=headers_dict)


def get_thumbnail_page(url: str) -> int:
    return int(THUMBNAIL_PAGE_PATTERN.match(url).group(1))


# this method isn't good enough, gotta try SSIM: https://stackoverflow.com/questions/71567315/how-to-get-the-ssim-comparison-score-between-two-images
def check_thumbnail(thumbnail_url: str, entry_path: Path) -> bool:
    thumbnail_img = Image.open(BytesIO(get_url(thumbnail_url).content))
    thumbnail_page = get_thumbnail_page(thumbnail_url)
    actual_img_path = next(islice(entry_path.iterdir(), thumbnail_page - 1, None))
    actual_img = Image.open(actual_img_path).convert("RGB")
    actual_img.thumbnail(thumbnail_img.size)

    try:

        diff = ImageChops.difference(thumbnail_img, actual_img)

        # calculate rms
        histo = diff.histogram()
        rms = math.sqrt(
            reduce(operator.add, map(lambda h, i: h * (i**2), histo, range(len(histo))))
            / (float(thumbnail_img.size[0]) * actual_img.size[1])
        )
        diff.save("diff.bmp")
        return rms < 600
    except ValueError as e:
        return False


def suggest_f(artist: str, title: str) -> Union[str, None]:
    response = get_url(f"{F_BASE_URL}/suggest/{artist} {title}")
    suggestions = [s for s in response.json() if s["link"].startswith("/hentai/")]

    matching_title = next(
        (
            suggestion
            for suggestion in suggestions
            if do_slugify(title) == do_slugify(suggestion["title"])
            or title == do_slugify(suggestion["title"])
        ),
        None,
    )
    if matching_title:
        # matching_thumbnail = check_thumbnail(matching_title["image"], entry_path)
        return f"{F_BASE_URL}{matching_title['link']}"
    return None


def search_f(artist: str, title: str) -> Union[str, None]:
    page = get_url(f"{F_BASE_URL}/search/{artist} {title}")
    soup = BeautifulSoup(page.text, "html.parser")
    for entry in soup.select("div[id^='content-']"):
        entry_title = entry.select("a.text-md")[0]
        if do_slugify(entry_title.text.strip()) == do_slugify(title):
            for entry_artist in entry.select("a.text-sm"):
                if do_slugify(entry_artist.text.strip()) == do_slugify(artist):
                    url = entry_title["href"]
                    if isinstance(url, list):
                        url = url[0]
                    return f"{F_BASE_URL}{url}"
    return None


def suggest_i(artist: str, title: str) -> Union[str, None]:
    response_title = get_url(
        f"{I_BASE_URL}/index.php?route=extension/module/me_ajax_search/search&search={title}"
    )
    response_artist = get_url(
        f"{I_BASE_URL}/index.php?route=extension/module/me_ajax_search/search&search={artist}"
    )
    suggestions = [
        *response_title.json()["products"],
        *response_artist.json()["products"],
    ]
    matching_title = next(
        (
            suggestion
            for suggestion in suggestions
            if do_slugify(title) == do_slugify(suggestion["name"])
        ),
        None,
    )
    if matching_title:
        url = matching_title["href"]
        return urljoin(url, urlparse(url).path)
    return None


def search_i(artist: str, title: str) -> Union[str, None]:
    page = get_url(f"{I_BASE_URL}/index.php?route=product/search&search={title}")
    soup = BeautifulSoup(page.text, "html.parser")

    for entry in soup.select("#product-search .main-products .product-thumb"):
        entry_title = entry.select(".name a")[0]
        entry_artist = entry.select(".stats a")[0]
        if do_slugify(entry_title.text.strip()) == do_slugify(title) and do_slugify(
            entry_artist.text.strip()
        ) == do_slugify(artist):
            url = entry_title["href"]
            if isinstance(url, list):
                url = url[0]
            return urljoin(url, urlparse(url).path)
    return None


def search_entry(
    artist: str, download_title: str, index_title: str
) -> Union[str, None]:
    search_fns = [suggest_f, search_f, suggest_i, search_i]
    for search_fn in search_fns:
        if url := search_fn(artist, download_title):
            return url
        if index_title != download_title:
            if url := search_fn(artist, index_title):
                return url
        if url := search_fn(artist, do_slugify(download_title)):
            return url
        if do_slugify(index_title) != do_slugify(download_title):
            if url := search_fn(artist, do_slugify(index_title)):
                return url
    return None


def fetch_metadata_f(url: str, entry_path: Path) -> Dict[str, str]:
    metadata = {
        "title": None,
        "artists": [],
        "parodies": None,
        "circles": None,
        "events": None,
        "magazines": None,
        "publishers": None,
        "pages": 0,
        "direction": None,
        "description": None,
        "tags": [],
        "thumbnail_page": 1,
        "category": None,
        "official_source": None,
        "date_archived": None,
        "date_published": None,
        "collections": None,
        "related": None,
    }
    metadata["official_source"] = url

    page = get_url(url)
    soup = BeautifulSoup(page.text, "html.parser")

    right_container = soup.select(
        "div[class^='block md:table-cell relative w-full align-top']"
    )[0]
    metadata["title"] = right_container.h1.text.strip()
    for row in right_container.find_all("div", recursive=False):
        divs = row.find_all("div", recursive=False)
        if len(divs) == 2:
            key = divs[0].text.strip()
            if key in F_MULTI_KEYS_MAPPING:
                metadata[F_MULTI_KEYS_MAPPING[key]] = [
                    a.text.strip() for a in divs[1].find_all("a")
                ]
            elif key == "Pages":
                metadata["pages"] = int(
                    PAGES_PATTERN.match(divs[1].text.strip()).group(1)
                )
            elif key in ["Direction", "Language"]:
                metadata[divs[0].text.strip().lower()] = divs[1].text.strip()
        else:
            tags = divs[0].select("a.inline-block")
            if tags:
                metadata["tags"] = [
                    a.text.strip() for a in tags if a.text.strip() != "+"
                ]
            else:
                metadata["description"] = "\n".join(
                    str(l) for l in divs[0].contents
                ).strip()

    metadata["category"] = "manga" if metadata["magazines"] else "doujinshi"

    collections = soup.select(
        "div[id$='/collections'] b > a:not([href^='/collections'])"
    )
    if collections:
        metadata["collections"] = [collection["href"] for collection in collections]

    related_entries = soup.select("div[id$='/related'] div[id^='content-']")
    if related_entries:
        metadata["related"] = [related.a["href"] for related in related_entries]

    chapters = soup.select("div[id$='/chapters'] div[id^='content-']")
    if chapters:
        raise Exception("woah, found one!")

    thumbnail_url = soup.select(
        "div[class^='block sm:inline-block relative w-full align-top'] img"
    )[0]["src"]
    if isinstance(thumbnail_url, list):
        thumbnail_url = thumbnail_url[0]

    metadata["thumbnail_page"] = get_thumbnail_page(thumbnail_url)
    thumbnail_img = get_url(thumbnail_url)
    metadata["date_published"] = parsedate_to_datetime(
        thumbnail_img.headers["last-modified"]
    ).isoformat()
    metadata["date_archived"] = datetime.fromtimestamp(
        os.path.getmtime(
            next(f for f in entry_path.iterdir() if f.suffix in IMAGE_SUFFIXES)
        )
    ).isoformat()
    return metadata


def fetch_metadata_i(url: str, entry_path: Path) -> Dict[str, str]:
    metadata = {
        "title": None,
        "artists": [],
        "parodies": None,
        "circles": None,
        "events": None,
        "magazines": None,
        "publishers": None,
        "pages": 0,
        "direction": None,
        "description": None,
        "tags": [],
        "thumbnail_page": 1,
        "category": None,
        "official_source": None,
        "date_archived": None,
        "date_published": None,
        "collections": None,
        "related": None,
    }
    metadata["official_source"] = url
    metadata["parodies"] = ["Original Work"]
    metadata["publishers"] = ["Irodori Comics"]
    metadata["category"] = "doujinshi"

    page = get_url(url)
    soup = BeautifulSoup(page.text, "html.parser")

    metadata["title"] = soup.select("h1.page-title")[0].text.strip()

    main_container = soup.select("#product-product #content .product-info")[0]
    right_container = main_container.select(".product-right")[0]
    metadata["artists"] = [
        artist.text.strip()
        for artist in right_container.select(".product-manufacturer a")
    ]
    metadata["pages"] = int(right_container.select(".product-upc span")[0].text.strip())
    metadata["description"] = "\n".join(
        str(l)
        for l in right_container.select(".product_extra .block-content")[0].contents
    ).strip()
    metadata["tags"] = [
        tag.text.strip()
        for tag in right_container.select(".tags a")
        if tag.text.strip()
    ]
    left_container = main_container.select(".product-left")[0]
    thumbnail_url = left_container.select(".main-image img")[0]["src"]
    if isinstance(thumbnail_url, list):
        thumbnail_url = thumbnail_url[0]

    thumbnail_img = get_url(thumbnail_url)
    metadata["date_published"] = parsedate_to_datetime(
        thumbnail_img.headers["last-modified"]
    ).isoformat()
    metadata["date_archived"] = (
        datetime.fromtimestamp(
            int(
                os.path.getmtime(
                    next(f for f in entry_path.iterdir() if f.suffix in IMAGE_SUFFIXES)
                )
            )
        )
        .astimezone(pytz.utc)
        .isoformat()
    )
    return metadata


def fetch_all():
    global downloaded_data
    global index_data
    global original_sources_data
    for artist, entries in index_data.items():
        for entry, url in entries.items():
            source_url = original_sources_data.get(url, None)
            if not source_url:
                source_url = search_entry(
                    artist,
                    clean_directory_name(downloaded_data[url]),
                    clean_directory_name(entry),
                )
                if not source_url:
                    log.error(f"could not find source for {artist}/{entry}")
                    continue
                log.info(f"found source for {artist}/{entry}   ---   {source_url}")
                original_sources_data[url] = source_url
                with original_sources_json.open("r+", encoding="utf-8") as f:
                    original_sources_data = dict(
                        sorted(original_sources_data.items(), key=lambda item: item[1])
                    )
                    f.seek(0)
                    json.dump(
                        obj=original_sources_data, fp=f, indent=2, ensure_ascii=False
                    )
                    f.write("\n")
                    f.truncate()

            entry_path = data_dir / artist / entry
            if source_url.startswith(F_BASE_URL):
                pass
                # metadata = fetch_metadata_f(source_url, entry_path)
            elif source_url.startswith(I_BASE_URL):
                pass
                # metadata = fetch_metadata_i(source_url, entry_path)
            elif source_url.startswith("https://exhentai.org/"):
                pass
                # make a local metadata provider? i dont wanna scrape that mfer
            else:
                raise Exception("unknown source type")


fetch_all()
