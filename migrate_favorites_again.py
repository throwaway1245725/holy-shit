import json
import re
from pathlib import Path
from typing import Dict

index_json = Path.cwd() / "index.json"
favorited_ksk_json = Path.cwd() / "favorited_ksk.json"
favorited_anchira_json = Path.cwd() / "favorited_anchira.json"

with index_json.open("r", encoding="utf-8") as f:
    index_data: Dict[str, Dict[str, str]] = json.load(f)

ANCHIRA_PATTERN = re.compile(r"https:\/\/anchira\.to\/g\/(\d+)\/.*")


def compare_favorite_urls():
    with favorited_ksk_json.open("r", encoding="utf-8") as f:
        favorited_ksk_data: Dict[str, str] = json.load(f)
    with favorited_anchira_json.open("r", encoding="utf-8") as f:
        favorited_anchira_data: Dict[str, str] = json.load(f)
    favorited_ksk_ids: set[str] = set(
        m.group(1)
        for url in favorited_ksk_data.keys()
        if (m := ANCHIRA_PATTERN.match(url))
    )
    favorited_anchira_ids = set(
        m.group(1)
        for url in favorited_anchira_data.keys()
        if (m := ANCHIRA_PATTERN.match(url))
    )
    print(favorited_ksk_ids - favorited_anchira_ids)


compare_favorite_urls()
