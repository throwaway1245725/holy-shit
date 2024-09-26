import json
import os
import re
import shutil
import sys
import zipfile
from email.message import Message
from pathlib import Path

import requests
from dotenv import load_dotenv
from tqdm import tqdm

parent_dir = Path(__file__).parent

sys.path.append(parent_dir.parent.as_posix())
from clean_favorited import switch_all_urls
from hn.download_favorited import clean_download_index, download_archive
from log_setup import log
from process_downloaded import clean_filenames

load_dotenv(parent_dir.parent / ".env")

HN_BASE_URL = os.getenv("HN_BASE_URL", "")
HN_ID_PATTERN = re.compile(f"{re.escape(HN_BASE_URL)}/view/(\\d+)")


data_dir = parent_dir.parent / "data"
download_dir = parent_dir.parent / "downloaded"

url_map_json = parent_dir.parent / "url_map.json"
with url_map_json.open("r", encoding="utf-8") as f:
    url_map: dict[str, str] = json.load(f)

downloaded_json = parent_dir.parent / "downloaded.json"

index_json = parent_dir.parent / "index.json"
with index_json.open(mode="r", encoding="utf-8") as f:
    index_data: dict[str, dict[str, str]] = json.load(f)

favorited_json = parent_dir / "favorited.json"

cookies_txt = parent_dir / "hn_cookies.txt"
with cookies_txt.open("r") as f:
    cookies_str = f.read()
    cookies_dict = {
        cookie.split("=")[0]: cookie.split("=")[1] for cookie in cookies_str.split("; ")
    }


def delete_from_downloaded_data(url):
    with downloaded_json.open("r+", encoding="utf-8") as f:
        downloaded_data: dict[str, str] = json.load(f)
        del downloaded_data[url]
        downloaded_data = dict(
            sorted(downloaded_data.items(), key=lambda item: item[1])
        )
        f.seek(0)
        json.dump(obj=downloaded_data, fp=f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.truncate()


def replace_contents(orig_url, new_url):
    with downloaded_json.open("r", encoding="utf-8") as f:
        downloaded_data: dict[str, str] = json.load(f)
    artist, entry = next(
        (artist, entry)
        for artist, entries in index_data.items()
        for entry, url in entries.items()
        if url == orig_url
    )
    log.info(f"replacing contents of {artist}/{entry}")
    archive = download_dir / f"{downloaded_data[new_url]}.cbz"
    entry_path = data_dir / artist / entry
    for file_to_delete in filter(
        lambda f: f.name != "metadata.json", entry_path.iterdir()
    ):
        file_to_delete.unlink()
    with zipfile.ZipFile(archive, "r") as zip:
        zip.extractall(entry_path)

    log.info(f'updating hn favorited entry "{new_url}": "{artist}/{entry}"')
    with favorited_json.open("r+", encoding="utf-8") as f:
        favorited_data: dict[str, str] = json.load(f)
        favorited_data[new_url] = f"{artist}/{entry}"
        favorited_data = dict(sorted(favorited_data.items(), key=lambda item: item[1]))
        f.seek(0)
        json.dump(obj=favorited_data, fp=f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.truncate()


def download_all_replacements():
    with downloaded_json.open("r", encoding="utf-8") as f:
        downloaded_data: dict[str, str] = json.load(f)
    with favorited_json.open("r", encoding="utf-8") as f:
        favorited_data: dict[str, str] = json.load(f)
    replacements = {
        k_url: hn_url
        for hn_url, k_url in url_map.items()
        if k_url in downloaded_data.keys() and hn_url in favorited_data.keys()
    }
    for k_url, hn_url in replacements.items():
        log.info(f"replacing {k_url} with {hn_url}")
        file_to_delete = download_dir / f"{downloaded_data[k_url]}.cbz"
        log.info(f"deleting downloaded file: {file_to_delete}")
        file_to_delete.unlink()
        delete_from_downloaded_data(k_url)
        download_archive(hn_url)
        replace_contents(k_url, hn_url)


def main():
    clean_download_index()
    download_all_replacements()
    switch_all_urls("hn")
    clean_filenames()


if __name__ == "__main__":
    main()
