import collections
import json
import re
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Dict

import requests
import yaml
from bs4 import BeautifulSoup
from tinydb import TinyDB

KSK_DED = True

PLURAL_MAP = {
    "artist": "artists",
    "circle": "circles",
    "magazine": "magazines",
    "parody": "parodies",
    "tag": "tags",
}
PAGES_PATTERN = re.compile(r"\/browse\?ps=(?P<pages>\d+)&adv=")
HREF_PATTERN = re.compile(r"\/.+\/(?P<name>.+)")

IMAGE_SUFFIXES = [".jpg", ".jpeg", ".png"]

index_json = Path.cwd() / "index.json"
data_dir = Path.cwd() / "data"
db = TinyDB("db.json", indent=2, ensure_ascii=False, sort_keys=True, encoding="utf-8")


def resolve_external_url(ksk_url: str) -> str:
    response = requests.get(f"https://ksk.moe{ksk_url}")
    return response.url


def get_local_metadata(entry_path: Path):
    yaml_file = next(file for file in entry_path.iterdir() if file.suffix == ".yaml")
    print(f"found metadata file: {yaml_file}")
    with yaml_file.open("r") as f:
        yaml_data = yaml.safe_load(f)

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

    metadata["title"] = yaml_data["Title"]

    metadata["artists"] = yaml_data.get("Artist", [])
    metadata["circles"] = yaml_data.get("Circle", None)
    artists_str = ",".join(metadata["artists"])
    circles_str = ",".join(metadata["circles"]) if metadata["circles"] else ""
    metadata[
        "archive_name"
    ] = f"[{f'{circles_str}[{artists_str}]' if circles_str else artists_str}] {entry_path.name}"

    metadata["category"] = "Manga" if "Magazine" in yaml_data.keys() else "Doujinshi"
    metadata["magazines"] = yaml_data.get("Magazine", None)
    metadata["parodies"] = yaml_data.get("Parody", None)
    metadata["tags"] = yaml_data["Tags"]
    metadata["pages"] = yaml_data["Pages"]
    metadata["official_sources"] = {
        "display_name": ",".join(yaml_data.get("Publisher", ["FAKKU"])),
        "url": yaml_data["URL"],
    }

    size_in_bytes = sum(
        image.stat().st_size
        for image in entry_path.iterdir()
        if image.suffix in IMAGE_SUFFIXES
    )
    metadata[
        "size"
    ] = f"{round(size_in_bytes / ((2**10)**2))} MiB ({size_in_bytes:,} bytes)"

    epoch = yaml_data.get("Released", None)
    if epoch:
        date_dict = {
            "display": datetime.fromtimestamp(epoch).strftime("%d.%m.%Y %H:%M UTC"),
            "epoch": epoch,
        }
        metadata["date_archived"] = date_dict
        metadata["date_published"] = date_dict
        metadata["date_updated"] = date_dict
        metadata["date_uploaded"] = date_dict

    metadata["description"] = yaml_data.get("Description", None)

    return metadata


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


def check_duplicates(index_data):
    duplicate_urls = set(
        item
        for item, count in collections.Counter(
            url
            for _artist, entries in index_data.items()
            for _entry, url in entries.items()
            if url
        ).items()
        if count > 1
    )
    if duplicate_urls:
        duplicate_urls_str = "\n".join(
            f"{artist}/{entry}:{url}"
            for artist, entries in index_data.items()
            for entry, url in entries.items()
            if url in duplicate_urls
        )
        print(f"duplicate urls detected: \n{duplicate_urls_str}")


def get_missing_metadata():
    print("fetching missing metadata")
    with index_json.open(mode="r", encoding="utf-8") as f:
        index_data: Dict[str, Dict[str, str]] = json.load(f)

    check_duplicates(index_data)

    for artist, entries in index_data.items():
        for entry, url in entries.items():
            metadata_json = data_dir / artist / entry / "metadata.json"

            if not metadata_json.exists():
                try:
                    if KSK_DED:
                        raise Exception("ksk ded")
                    print(f"fetching metadata for {artist}/{entry}")
                    metadata = get_metadata(url)
                    write_metadata(metadata_json, metadata)
                except Exception as e:
                    if not KSK_DED:
                        print(f"failed to fetch metadata for {url}")
                        print(e)
                    try:
                        print(f"fetching local metadata for {artist}/{entry}")
                        metadata = get_local_metadata(data_dir / artist / entry)
                        write_metadata(metadata_json, metadata)
                    except Exception as e:
                        print(f"failed to fetch local metadata for {artist}/{entry}")
                        print(e)


def write_metadata(metadata_json, metadata):
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


get_missing_metadata()
