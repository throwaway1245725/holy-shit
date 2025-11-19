import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

parent_dir = Path(__file__).parent

sys.path.append(parent_dir.parent.as_posix())
from log_setup import log

load_dotenv(parent_dir.parent / ".env")

K_BASE_URL = os.getenv("K_BASE_URL", "")
K_API_URL = os.getenv("K_API_URL", "")
IGNORE_ALREADY_PROCESSED = (
    os.getenv("IGNORE_ALREADY_PROCESSED", "true").lower() == "true"
)
PRETTY_JSON = os.getenv("PRETTY_JSON", "true").lower() == "true"

favorited_json = parent_dir / "favorited.json"

localstorage_json = parent_dir / "k_localstorage.json"
with localstorage_json.open("r") as f:
    localstorage_dict: dict[str, Any] = json.load(f)


def get_url(url: str, params=None) -> requests.Response:
    default_params = {"crt": localstorage_dict["clearance"]}
    return requests.get(
        url,
        params=default_params if not params else params | default_params,
        headers={
            "Authorization": f"Bearer {localstorage_dict["token"]["session"]}",
            "Origin": K_BASE_URL,
            "Referer": f"{K_BASE_URL}/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        },
    )


def parse_favorite_page(page_num: int) -> bool:
    page = get_url(f"{K_API_URL}/books/favorites", params={"page": page_num})
    with favorited_json.open("r+", encoding="utf-8") as f:
        favorited_data: dict[str, str] = json.load(f)
        reached_already_processed = False
        for entry in page.json()["entries"]:
            link: str = f"{K_BASE_URL}/g/{entry['id']}/{entry['key']}"
            title: str = entry["title"]
            if link not in favorited_data.keys():
                favorited_data[link] = f"!<not yet downloaded> {title}"
            else:
                reached_already_processed = True
                break

        if PRETTY_JSON:
            favorited_data = dict(
                sorted(favorited_data.items(), key=lambda item: item[1])
            )
        f.seek(0)
        json.dump(
            obj=favorited_data,
            fp=f,
            indent=2 if PRETTY_JSON else None,
            ensure_ascii=False,
        )
        f.write("\n")
        f.truncate()
        return reached_already_processed


def get_favorites():
    page = get_url(f"{K_API_URL}/books/favorites")
    page_data = page.json()
    num_pages: int = math.ceil(page_data["total"] / page_data["limit"])
    for page_num in range(1, num_pages):
        log.info(f"parsing page: {page_num}")
        reached_already_processed = parse_favorite_page(page_num)
        if IGNORE_ALREADY_PROCESSED and reached_already_processed:
            log.info("reached already processed, stopping")
            break


def main():
    get_favorites()


if __name__ == "__main__":
    main()
