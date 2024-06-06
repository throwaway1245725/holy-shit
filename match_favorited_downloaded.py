import json
import re
from pathlib import Path
from typing import Dict

from log_setup import log

download_dir = Path.cwd() / "downloaded"
downloaded_json = Path.cwd() / "downloaded.json"
favorited_json = Path.cwd() / "favorited.json"
with favorited_json.open(mode="r", encoding="utf-8") as f:
    favorited_data: Dict[str, str] = json.load(f)


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


def add_new_favorites():
    FAVORITE_FILENAME_PATTERN = re.compile(r"!<not yet downloaded> (.*)")
    for url, path in favorited_data.items():
        if m := FAVORITE_FILENAME_PATTERN.match(path):
            matching_archive = next(
                (
                    archive
                    for archive in download_dir.iterdir()
                    if archive.stem.startswith(m.group(1))
                ),
                None,
            )
            if matching_archive:
                log.info(f"found match for {path} - {matching_archive.stem}")
                with downloaded_json.open("r+", encoding="utf-8") as f:
                    downloaded_data: Dict[str, str] = json.load(f)
                    if url not in downloaded_data.keys():
                        downloaded_data[url] = matching_archive.stem
                        downloaded_data = dict(
                            sorted(downloaded_data.items(), key=lambda item: item[1])
                        )
                        f.seek(0)
                        json.dump(
                            obj=downloaded_data, fp=f, indent=2, ensure_ascii=False
                        )
                        f.write("\n")
                        f.truncate()
                    else:
                        log.error(f"url already exists in downloaded for {path}: {url}")
            else:
                log.info(f"no matching file for {path}")


clean_download_index()
add_new_favorites()
