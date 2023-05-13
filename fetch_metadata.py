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
    "magazine": "magazines",
    "parody": "parodies",
    "tag": "tags",
}
PAGES_PATTERN = re.compile(r"\/browse\?ps=(?P<pages>\d+)&adv=")
HREF_PATTERN = re.compile(r"\/.+\/(?P<name>.+)")

index_json = Path.cwd() / "index.json"
data_dir = Path.cwd() / "data"
db = TinyDB("db.json", indent=2, ensure_ascii=False, sort_keys=True, encoding="utf-8")


def resolve_external_url(ksk_url: str) -> str:
    response = requests.get(f"https://ksk.moe{ksk_url}")
    return response.url


def get_metadata(url):
    page = requests.get(url)
    soup = BeautifulSoup(page.text, "html.parser")
    soup_metadata = soup.find(id="metadata")
    if soup_metadata is None:
        raise Exception(f"============== bad url ==============")

    links = soup_metadata.find_all(class_="l")

    metadata = {
        "title": None,
        "archive_name": None,
        "category": None,
        "uploader": None,
        "artists": [],
        "circles": None,
        "magazines": None,
        "parodies": None,
        "tags": [],
        "pages": 0,
        "official_sources": None,
        "size": None,
        "date_uploaded": None,
        "date_archived": None,
        "date_published": None,
        "date_updated": None,
        "description": None,
    }

    metadata["title"] = soup_metadata.h1.text
    metadata["archive_name"] = soup_metadata.h2.text
    metadata["uploader"] = next(
        (
            div.div.text
            for div in soup_metadata.main.find_all("div", recursive=False)
            if div.strong.text == "Uploader"
        ),
        None,
    )

    for link in links:
        raw_type = link.parent.strong.text.lower()
        type = PLURAL_MAP[raw_type] if raw_type in PLURAL_MAP else raw_type
        entries = link.find_all("a")
        if not entries:
            raise Exception("============== no links found ==============")
        if type == "length":
            if len(entries) > 1:
                raise Exception("============== multiple page numbers ==============")
            metadata["pages"] = int(
                PAGES_PATTERN.match(entries[0]["href"]).group("pages")
            )
        elif type == "metadata":
            metadata["official_sources"] = [
                {
                    "url": resolve_external_url(entry["href"]),
                    "display_name": entry.span.text,
                }
                for entry in entries
            ]
        else:
            data = [entry.span.text for entry in entries]
            if type not in PLURAL_MAP.values():
                if len(entries) > 1:
                    raise Exception("============== unexpected list ==============")
                data = data[0]
            metadata[type] = data

    metadata["size"] = next(
        div.div.text.strip().replace("\n", " ")
        for div in soup_metadata.main.find_all("div", recursive=False)
        if div.strong.text == "Size (Ori.)"
    )

    uploaded = next(
        div.div.time
        for div in soup_metadata.main.find_all("div", recursive=False)
        if div.strong.text == "Uploaded"
    )
    metadata["date_uploaded"] = {
        "epoch": int(uploaded["data-timestamp"]),
        "display": uploaded.text.strip(),
    }
    archived = soup_metadata.find(class_="created")
    metadata["date_archived"] = {
        "epoch": int(archived["data-timestamp"]),
        "display": archived.text.strip(),
    }
    published = soup_metadata.find(class_="published")
    metadata["date_published"] = {
        "epoch": int(published["data-timestamp"]),
        "display": published.text.strip(),
    }
    updated = soup_metadata.find(class_="updated")
    metadata["date_updated"] = {
        "epoch": int(updated["data-timestamp"]),
        "display": updated.text.strip(),
    }

    soup_description = soup.find(id="description")
    if soup_description:
        metadata["description"] = soup_description.main.text.strip()

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
                try:
                    metadata = get_metadata(url)
                    with metadata_json.open(mode="w", encoding="utf-8") as f:
                        json.dump(
                            obj=metadata,
                            fp=f,
                            indent=2,
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        f.write("\n")
                    db.insert(
                        {
                            **metadata,
                            "json_path": metadata_json.relative_to(data_dir).as_posix(),
                        }
                    )
                except Exception as e:
                    print(f"failed to fetch metadata for {url}")
                    print(e)


get_missing_metadata()
