import json
import re
import urllib.parse
from pathlib import Path
from typing import Dict, Tuple

import requests
from bs4 import BeautifulSoup

ALPHANUM_PATTERN = re.compile(r"[^A-Za-z0-9 ]+")
URL_PATTERN = re.compile(r"(.*) ===> (.*)")

index_json = Path.cwd() / "index.json"
data_dir = Path.cwd() / "data"
url_migration_csv = Path.cwd() / "url_migration.csv"

with index_json.open(mode="r", encoding="utf-8") as f:
    index_data: Dict[str, Dict[str, str]] = json.load(f)

already_migrated_urls = []
if url_migration_csv.exists():
    with url_migration_csv.open("r", encoding="utf-8") as f:
        already_migrated_urls = [
            m.group(1)
            for line in f.readlines()
            if (m := URL_PATTERN.match(line)) and len(m.groups()) == 2
        ]


def do_migration():
    for artist, entries in index_data.items():
        for entry, url in entries.items():
            if url not in already_migrated_urls:
                metadata_json = data_dir / artist / entry / "metadata.json"
                with metadata_json.open(mode="r", encoding="utf-8") as f:
                    metadata = json.load(f)
                artist_search = f'artist:"{artist}"'
                title_search = f'title:"{metadata["title"]}"'
                # magazines_search = (
                #     " ".join(
                #         f'magazine:"{magazine["display_name"]}"'
                #         for magazine in metadata["magazines"]
                #     )
                #     if metadata["magazines"]
                #     else ""
                # )
                # tags_search = " ".join(
                #     f'tag:"{tag["display_name"]}"' for tag in metadata["tags"]
                # )
                search_url = f'https://ksk.moe/browse?s={urllib.parse.quote_plus(" ".join([artist_search, title_search]))}'

                page = requests.get(search_url)
                soup = BeautifulSoup(page.text, "html.parser").find(id="galleries")

                links = soup.find_all("a")

                if len(links) > 1:
                    all_links = list(links)
                    links = [
                        link
                        for link in links
                        if re.sub(ALPHANUM_PATTERN, "", link["title"])
                        == re.sub(ALPHANUM_PATTERN, "", metadata["title"])
                    ]

                if len(links) != 1:
                    raise Exception(f"{url} ===> ")

                with url_migration_csv.open(mode="a", encoding="utf-8") as f:
                    f.write(f"{url} ===> https://ksk.moe{links[0]['href']}\n")


def verify_migration():
    def parse_line(line: str) -> Tuple[str, str]:
        m = URL_PATTERN.match(line)
        if len(m.groups()) != 2:
            raise Exception("what!?")
        return m.group(1), m.group(2)

    with url_migration_csv.open(mode="r", encoding="utf-8") as f:
        entries = [parse_line(line) for line in f.readlines()]
        print(entries)


do_migration()
verify_migration()
