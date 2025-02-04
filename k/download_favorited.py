import json
import os
import re
import sys
from datetime import datetime, timedelta
from email.message import Message
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from tqdm import tqdm

parent_dir = Path(__file__).parent

sys.path.append(parent_dir.parent.as_posix())
from log_setup import log

load_dotenv(parent_dir.parent / ".env")

K_BASE_URL = os.getenv("K_BASE_URL", "")
K_API_URL = os.getenv("K_API_URL", "")
K_ID_PATTERN = re.compile(f"{re.escape(K_BASE_URL)}/g/(\\d+)/(.*)")


download_dir = parent_dir.parent / "downloaded"
downloaded_json = parent_dir.parent / "downloaded.json"

url_map_json = parent_dir.parent / "url_map.json"
with url_map_json.open("r", encoding="utf-8") as f:
    url_map: dict[str, str] = {k_url: hn_url for hn_url, k_url in json.load(f).items()}

favorited_json = parent_dir / "favorited.json"
with favorited_json.open("r", encoding="utf-8") as f:
    favorited_data: dict[str, str] = json.load(f)

localstorage_json = parent_dir / "k_localstorage.json"
with localstorage_json.open("r") as f:
    localstorage_dict: dict[str, Any] = json.load(f)

HEADERS = {"Origin": K_BASE_URL, "Referer": f"{K_BASE_URL}/"}
ACCESS_TOKEN = localstorage_dict["token"]["session"]


def clean_download_index():
    downloaded_archives = set(archive.stem for archive in download_dir.iterdir())
    with downloaded_json.open("r+", encoding="utf-8") as f:
        downloaded_data: dict[str, str] = json.load(f)
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


def extract_filename(headers):
    msg = Message()
    msg["content-disposition"] = headers["content-disposition"]
    filename = msg.get_filename()
    if filename:
        return re.sub(r"[<>:\"/\\|?*]", "_", filename)
    else:
        raise Exception("not supposed to happen!")


def download_file(filepath: Path, response: requests.Response, file_size: int):
    if filepath.exists():
        raise Exception("file already exists?!")
    chunk_size = 1024 * 16
    with open(filepath, "wb") as f:
        with tqdm(
            total=file_size,
            desc=f"Downloading {filepath.name}",
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            miniters=1,
        ) as bar:
            for chunk in response.iter_content(chunk_size=chunk_size):
                f.write(chunk)
                bar.update(chunk_size)


def write_to_downloaded_json(url: str, filename: str):
    with downloaded_json.open("r+", encoding="utf-8") as f:
        downloaded_data: dict[str, str] = json.load(f)
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
    if m := K_ID_PATTERN.match(url):
        details_url = f"{K_API_URL}/books/detail/{m.group(1)}/{m.group(2)}"
        details_r = requests.get(details_url, headers=HEADERS)
        dl_details = details_r.json()

        if "id" not in dl_details:
            log.error(f"could not download {dl_details['title']}, not available yet")
            days_to_wait = (
                datetime.fromtimestamp(dl_details["created_at"] / 1e3)
                + timedelta(days=29)
                - datetime.today()
            ).days
            log.error(f"try again in {days_to_wait} days")
            return
        dl_pre_url = f"{K_API_URL}/books/data/{m.group(1)}/{m.group(2)}/{dl_details['id']}/{dl_details['key']}/0"
        pre_url_r = requests.post(
            dl_pre_url,
            params={"action": "dl"},
            data={"token": ACCESS_TOKEN},
            headers=HEADERS,
        )
        dl_url = pre_url_r.json()["base"]

        with requests.get(
            dl_url,
            params={"w": 0},
            headers=HEADERS,
            stream=True,
        ) as r:
            filepath = download_dir / extract_filename(r.headers)
            download_file(filepath, r, dl_details["size"])
            log.info(f"finished downloading '{url} : {filepath}'")
            if filepath.suffix != ".cbz":
                filepath_cbz = filepath.with_suffix(".cbz")
                filepath.rename(filepath_cbz)
                filepath = filepath_cbz
                log.info(f"renamed zip to cbz: {filepath}")
            write_to_downloaded_json(url, filepath.stem)


def download_all_favorites():
    for url, path in favorited_data.items():
        with downloaded_json.open("r", encoding="utf-8") as f:
            downloaded_data: dict[str, str] = json.load(f)
        if not (
            url in downloaded_data.keys()
            or url_map.get(url, None) in downloaded_data.keys()
        ):
            log.info(f"downloading favorite: '{url} : {path}'")
            download_archive(url)


def main():
    clean_download_index()
    download_all_favorites()


if __name__ == "__main__":
    main()
