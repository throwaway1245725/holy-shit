import json
import os
import re
import shutil
import sys
from email.message import Message
from pathlib import Path
from time import sleep
from typing import Dict

import requests
from dotenv import load_dotenv
from tqdm import tqdm

sys.path.append(Path(__file__).parent.parent.as_posix())
from log_setup import log

load_dotenv(Path(__file__).parent.parent / ".env")

HN_BASE_URL = os.getenv("HN_BASE_URL", "")
HN_ID_PATTERN = re.compile(f"{re.escape(HN_BASE_URL)}/view/(\\d+)")


download_dir = Path(__file__).parent.parent / "downloaded"
favorited_json = Path(__file__).parent / "favorited.json"
downloaded_json = Path(__file__).parent.parent / "downloaded.json"

with favorited_json.open("r", encoding="utf-8") as f:
    favorited_data: Dict[str, str] = json.load(f)

cookies_txt = Path(__file__).parent / "hn_cookies.txt"
with cookies_txt.open("r") as f:
    cookies_str = f.read()
    cookies_dict = {
        cookie.split("=")[0]: cookie.split("=")[1] for cookie in cookies_str.split("; ")
    }


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


def download_all_favorites():
    for url, path in favorited_data.items():
        with downloaded_json.open("r", encoding="utf-8") as f:
            downloaded_data: Dict[str, str] = json.load(f)
        if not url in downloaded_data.keys():
            log.info(f"downloading favorite: '{url} : {path}'")
            download_archive(url)


def extract_filename(headers):
    msg = Message()
    msg["content-disposition"] = headers["content-disposition"]
    filename = msg.get_filename()
    if filename:
        return re.sub(r"[<>:\"/\\|?*]", "_", filename)
    else:
        raise Exception("not supposed to happen!")


def download_file(filepath: Path, response: requests.Response):
    if filepath.exists():
        raise Exception("file already exists?!")
    file_size = int(response.headers["content-length"])
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


def download_archive(url):
    if m := HN_ID_PATTERN.match(url):
        dl_url = f"{HN_BASE_URL}/zip/{m.group(1)}"
        with requests.get(dl_url, stream=True, cookies=cookies_dict) as r:
            filepath = download_dir / extract_filename(r.headers)
            download_file(filepath, r)
            log.info(f"finished downloading '{url} : {filepath}'")
            if filepath.suffix != ".cbz":
                filepath_cbz = filepath.with_suffix(".cbz")
                filepath.rename(filepath_cbz)
                filepath = filepath_cbz
                log.info(f"renamed zip to cbz: {filepath}")
            write_to_downloaded_json(url, filepath.stem)


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


def main():
    clean_download_index()
    download_all_favorites()


if __name__ == "__main__":
    main()
