import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Set, Tuple, Union

from log_setup import log

favorited_json = Path.cwd() / "favorited.json"
index_json = Path.cwd() / "index.json"

with index_json.open(mode="r", encoding="utf-8") as f:
    index_data: Dict[str, Dict[str, str]] = json.load(f)


def clean_favorited():
    with favorited_json.open("r+", encoding="utf-8") as f:
        favorited_data: Dict[str, str] = json.load(f)
        for entry_url, entry_name in (
            (url, entry_name)
            for url, entry_name in favorited_data.items()
            if entry_name.startswith("!<not yet downloaded>")
        ):
            favorited_data[entry_url] = next(
                f"{artist}/{entry}"
                for artist, entries in index_data.items()
                for entry, url in entries.items()
                if url == entry_url
            )
            log.info(f"renaming {entry_name} to {favorited_data[entry_url]}")
        favorited_data = dict(sorted(favorited_data.items(), key=lambda item: item[1]))
        f.seek(0)
        json.dump(obj=favorited_data, fp=f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.truncate()


clean_favorited()
