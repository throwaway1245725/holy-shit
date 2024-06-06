import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Union

import requests
from bs4 import BeautifulSoup, Tag
from tinydb import TinyDB, where

from log_setup import log

HN_BASE_URL = os.getenv("HN_BASE_URL", "")

data_dir = Path.cwd() / "data"

a_index_archive_json = Path.cwd() / "a_index_archive.json"
with a_index_archive_json.open(mode="r", encoding="utf-8") as f:
    a_index_archive_data: Dict[str, Dict[str, str]] = json.load(f)

a_favorited_archive_json = Path.cwd() / "a_favorited_archive.json"
with a_favorited_archive_json.open(mode="r", encoding="utf-8") as f:
    a_favorited_archive_data: Dict[str, str] = json.load(f)

index_json = Path.cwd() / "index.json"
with index_json.open(mode="r", encoding="utf-8") as f:
    index_data: Dict[str, Dict[str, str]] = json.load(f)

downloaded_json = Path.cwd() / "downloaded.json"
with downloaded_json.open(mode="r", encoding="utf-8") as f:
    downloaded_data: Dict[str, str] = json.load(f)

original_sources_json = Path.cwd() / "original_sources.json"
with original_sources_json.open(mode="r", encoding="utf-8") as f:
    original_sources_data: Dict[str, str] = json.load(f)

favorited_json = Path.cwd() / "favorited.json"
with favorited_json.open(mode="r", encoding="utf-8") as f:
    favorited_data: Dict[str, str] = json.load(f)

missing_json = Path.cwd() / "missing.json"
with missing_json.open(mode="r", encoding="utf-8") as f:
    missing_data: Dict[str, Dict[str, Any]] = json.load(f)


cookies_txt = Path.cwd() / "hn_cookies.txt"
with cookies_txt.open("r") as f:
    cookies_str = f.read()
    cookies_dict = {
        cookie.split("=")[0]: cookie.split("=")[1] for cookie in cookies_str.split("; ")
    }

db = TinyDB("db.json", indent=2, ensure_ascii=False, sort_keys=True, encoding="utf-8")


def clean_bad_chars(name: str):
    new_name = re.sub(re.escape('"'), " ", name)
    new_name = re.sub(re.escape("'"), " ", new_name)
    new_name = re.sub(re.escape("."), " ", new_name)
    new_name = re.sub(re.escape(","), " ", new_name)
    new_name = re.sub(re.escape("!"), " ", new_name)
    new_name = re.sub(re.escape("?"), " ", new_name)
    new_name = re.sub(re.escape("&"), " ", new_name)
    new_name = re.sub(re.escape("-"), " ", new_name)
    new_name = re.sub(re.escape("+"), " ", new_name)
    new_name = re.sub(re.escape("~"), " ", new_name)
    new_name = re.sub(re.escape("♀"), " ", new_name)
    new_name = re.sub(re.escape("("), " ", new_name)
    new_name = re.sub(re.escape(")"), " ", new_name)
    new_name = re.sub(re.escape("]"), " ", new_name)
    new_name = re.sub(re.escape("["), " ", new_name)
    new_name = re.sub(re.escape("←"), " ", new_name)
    new_name = re.sub(re.escape("→"), " ", new_name)
    return new_name.strip()


def get_url(url: str, params: Dict[str, str]) -> requests.Response:
    return requests.get(url, params=params, cookies=cookies_dict)


def search_hn(artist: str, title: str) -> Union[str, None]:
    query_str = f'"{artist}" title:"{clean_bad_chars(title)}"'
    log.info(f"searching for '{query_str}'")
    page = get_url(
        f"{HN_BASE_URL}",
        {"q": query_str},
    )
    soup = BeautifulSoup(page.text, "html.parser")
    for entry in soup.select("a[href^='/view/'] > .card"):
        entry_title = entry.find("header")
        if (
            isinstance(entry_title, Tag)
            and entry_title.p
            and entry_title.p.text == title
        ):
            link_el = entry.parent
            if link_el:
                url = f"{HN_BASE_URL}{link_el['href']}"
                log.info(f"found match: {url}")
                return url
    return None


def search_all():
    global favorited_data
    for artist, entries in a_index_archive_data.items():
        for entry, url in entries.items():
            if f"{artist}/{entry}" in favorited_data.values():
                continue

            metadata_entries = db.search(
                where("json_path") == f"{artist}/{entry}/metadata.json"
            )
            if len(metadata_entries) != 1:
                log.error("mismatch in db")
                continue

            metadata_entry = metadata_entries[0]
            for metadata_artist in metadata_entry["artists"]:
                url = search_hn(metadata_artist, metadata_entry["title"])
                if url:
                    break

            if not url:
                log.error(f"no match found for {artist}/{entry}")
                continue

            with favorited_json.open("r+", encoding="utf-8") as f:
                favorited_data = json.load(f)
                favorited_data[url] = f"{artist}/{entry}"

                favorited_data = dict(
                    sorted(favorited_data.items(), key=lambda item: item[1])
                )
                f.seek(0)
                json.dump(obj=favorited_data, fp=f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.truncate()


def migrate_original_source_urls():
    global original_sources_data
    flipped_favorited = {entry_path: url for url, entry_path in favorited_data.items()}
    a_to_hn_map = {
        a_url: flipped_favorited[entry_path]
        for a_url, entry_path in a_favorited_archive_data.items()
    }
    original_sources_data = {
        (
            a_to_hn_map[entry_url]
            if entry_url.startswith("https://anchira.to")
            else entry_url
        ): source_url
        for entry_url, source_url in original_sources_data.items()
    }
    with original_sources_json.open("r+", encoding="utf-8") as f:
        original_sources_data = dict(
            sorted(original_sources_data.items(), key=lambda item: item[1])
        )
        f.seek(0)
        json.dump(
            obj=original_sources_data,
            fp=f,
            indent=2,
            ensure_ascii=False,
        )
        f.write("\n")
        f.truncate()


def migrate_index():
    global index_data
    flipped_favorited = {entry_path: url for url, entry_path in favorited_data.items()}
    a_to_hn_map = {
        a_url: flipped_favorited[entry_path]
        for a_url, entry_path in a_favorited_archive_data.items()
    }
    index_data = {
        artist: {
            entry: (
                a_to_hn_map[entry_url]
                if entry_url.startswith("https://anchira.to")
                else entry_url
            )
            for entry, entry_url in entries.items()
        }
        for artist, entries in index_data.items()
    }
    with index_json.open("w", encoding="utf-8") as f:
        json.dump(
            obj=index_data,
            fp=f,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        f.write("\n")


def add_missing_favorited():
    global favorited_data
    global index_data
    urls_missing_from_favorited = set(
        url for artist, entries in index_data.items() for entry, url in entries.items()
    ) - set(url for url, entry in favorited_data.items())
    url_to_path = {
        url: path
        for artist, entries in index_data.items()
        for path, url in entries.items()
    }
    for url in urls_missing_from_favorited:
        favorited_data[url] = url_to_path[url]

    with favorited_json.open("r+", encoding="utf-8") as f:
        favorited_data = dict(sorted(favorited_data.items(), key=lambda item: item[1]))
        f.seek(0)
        json.dump(obj=favorited_data, fp=f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.truncate()


def add_to_favorites(entry_path: str, url: str):
    global favorited_data
    HN_ID_PATTERN = re.compile(f"{re.escape(HN_BASE_URL)}/view/(\\d+)")
    if m := HN_ID_PATTERN.match(url):
        id = m.group(1)
        if send_favorite_request(entry_path, id):
            with favorited_json.open("r+", encoding="utf-8") as f:
                favorited_data = json.load(f)
                favorited_data[url] = entry_path

                favorited_data = dict(
                    sorted(favorited_data.items(), key=lambda item: item[1])
                )
                f.seek(0)
                json.dump(obj=favorited_data, fp=f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.truncate()


def send_favorite_request(entry_path: str, id: str):
    resp = requests.post(f"{HN_BASE_URL}/ajax/star/{id}", cookies=cookies_dict)
    if resp.ok:
        log.info(f"successfully favorited {entry_path}")
        return True
    else:
        log.error(
            f"error while trying to favorite {entry_path}: ({resp.status_code}) {resp.reason}"
        )
        return False


def re_favorite_everything():
    global index_data
    global favorited_data
    for artist, entries in index_data.items():
        for entry, url in entries.items():
            if url not in set(url for url, _ in favorited_data.items()):
                add_to_favorites(f"{artist}/{entry}", url)


def generate_missing():
    global missing_data
    global downloaded_data
    global index_data
    reverse_index = {
        url: f"{artist}/{entry}"
        for artist, entries in index_data.items()
        for entry, url in entries.items()
    }

    def get_relevant_info(url: str) -> Dict[str, Any]:
        metadata_entries = db.search(
            where("json_path") == f"{reverse_index[url]}/metadata.json"
        )
        if len(metadata_entries) != 1:
            log.error("mismatch in db")
            raise Exception()

        metadata_entry = metadata_entries[0]
        return {
            "title": metadata_entry["title"],
            "filepath": f"{downloaded_data[url]}.cbz",
            "official_source": metadata_entry["official_source"],
            "publishers": metadata_entry["publishers"],
            "is_tankoubon": "Book" in metadata_entry["tags"],
        }

    missing_data = {
        entry_path: get_relevant_info(url)
        for url, entry_path in reverse_index.items()
        if not url.startswith(HN_BASE_URL)
    }

    with missing_json.open("w", encoding="utf-8") as f:
        json.dump(
            obj=missing_data,
            fp=f,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        f.write("\n")


def generate_missing_metadata_file():
    global missing_data

    def get_all_metadata(entry_path: str):
        metadata_entries = db.search(
            where("json_path") == f"{entry_path}/metadata.json"
        )
        if len(metadata_entries) != 1:
            log.error("mismatch in db")
            raise Exception()
        metadata_entry = metadata_entries[0]
        return {k: v for k, v in metadata_entry.items() if k != "json_path"}

    all_metadata = {
        metadata["filepath"]: get_all_metadata(entry_path)
        for entry_path, metadata in missing_data.items()
    }
    all_metadata_json = Path.cwd() / "all_metadata.json"
    with all_metadata_json.open("w", encoding="utf-8") as f:
        json.dump(
            obj=all_metadata,
            fp=f,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        f.write("\n")


# search_all()
# migrate_original_source_urls()
# migrate_index()

# add_missing_favorited()
# re_favorite_everything()

# generate_missing()
# generate_missing_metadata_file()
