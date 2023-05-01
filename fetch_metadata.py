import json
import re
from pathlib import Path
from time import sleep
from typing import Dict

import requests
from bs4 import BeautifulSoup
from tinydb import TinyDB

PLURAL_MAP = {
    "artist": "artists",
    "circle": "circles",
    "official source": "official sources",
    "magazine": "magazines",
    "parody": "parodies",
    "tag": "tags",
}
PAGES_PATTERN = re.compile(r"\/browse\?ps=(?P<pages>\d+)&adv=")
HREF_PATTERN = re.compile(r"\/.+\/(?P<name>.+)")

index_json = Path.cwd() / "index.json"
data_dir = Path.cwd() / "data"


def get_metadata(url):
    page = requests.get(url)
    soup = BeautifulSoup(page.text, "html.parser").find(id="metadata")
    links = soup.find_all(class_="l")

    metadata = {
        "title": None,
        "archive_name": None,
        "artists": [],
        "magazines": None,
        "official_sources": None,
        "circles": None,
        "parodies": None,
        "tags": [],
        "pages": 0,
        "uploader": None,
        "size": None,
        "created_date": None,
        "uploaded_date": None,
    }

    metadata["title"] = soup.h1.text
    metadata["archive_name"] = soup.h2.text

    for link in links:
        raw_type = link.parent.strong.text.lower()
        type = PLURAL_MAP[raw_type] if raw_type in PLURAL_MAP else raw_type
        entries = link.find_all("a")
        if not entries:
            raise Exception("what")
        if type == "pages":
            if len(entries) > 1:
                raise Exception("fucken what now")
            metadata["pages"] = int(
                PAGES_PATTERN.match(entries[0]["href"]).group("pages")
            )
        elif type == "official sources":
            metadata["official_sources"] = [
                {
                    "url": entry["href"],
                    "display_name": entry.span.text,
                }
                for entry in entries
            ]
        else:
            data = [
                {
                    "name": HREF_PATTERN.match(entry["href"]).group("name"),
                    "display_name": entry.span.text,
                }
                for entry in entries
            ]
            if type not in PLURAL_MAP.values():
                if len(entries) > 1:
                    raise Exception("i fucken knew it")
                data = data[0]
            metadata[type] = data

    metadata["size"] = next(
        div.div.text
        for div in soup.find_all("div", recursive=False)
        if div.strong.text == "Size"
    )
    created = soup.find(class_="created")
    metadata["created_date"] = {
        "epoch": int(created["data-timestamp"]),
        "display": created.text.strip(),
    }

    uploaded = soup.find(class_="published")
    metadata["uploaded_date"] = {
        "epoch": int(uploaded["data-timestamp"]),
        "display": uploaded.text.strip(),
    }
    return metadata


def get_missing_metadata():
    print("fetching missing metadata")
    with index_json.open(mode="r", encoding="utf-8") as f:
        index_data: Dict[str, Dict[str, str]] = json.load(f)
    for artist, entries in index_data.items():
        for entry, url in entries.items():
            metadata_json = data_dir / artist / entry / "metadata.json"
            if not metadata_json.exists():
                print(f"fetching metadata for {artist}/{entry}")
                metadata = get_metadata(url)
                with metadata_json.open(mode="w", encoding="utf-8") as f:
                    json.dump(
                        obj=metadata, fp=f, indent=2, ensure_ascii=False, sort_keys=True
                    )
                    f.write("\n")
                try:
                    db = TinyDB("db.json", indent=2, ensure_ascii=False, sort_keys=True)
                    db.insert(
                        {
                            **metadata,
                            "json_path": metadata_json.relative_to(data_dir).as_posix(),
                        }
                    )
                except:
                    pass


get_missing_metadata()
