import collections
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from log_setup import log

load_dotenv()

HN_BASE_URL = os.getenv("HN_BASE_URL", "")

hn_favorited_json = Path(__file__).parent / "hn" / "favorited.json"
k_favorited_json = Path(__file__).parent / "k" / "favorited.json"

index_json = Path(__file__).parent / "index.json"
with index_json.open(mode="r", encoding="utf-8") as f:
    index_data: dict[str, dict[str, str]] = json.load(f)

url_map_json = Path(__file__).parent / "url_map.json"
with url_map_json.open(mode="r", encoding="utf-8") as f:
    url_map_data: dict[str, str] = json.load(f)


def clean_favorited(json_file: Path):
    with json_file.open("r+", encoding="utf-8") as f:
        favorited_data: dict[str, str] = json.load(f)
        for entry_url, entry_name in favorited_data.items():
            entry_path = next(
                (
                    f"{artist}/{entry}"
                    for artist, entries in index_data.items()
                    for entry, url in entries.items()
                    if url == entry_url or url == url_map_data.get(entry_url, None)
                ),
                favorited_data[entry_url],
            )
            if favorited_data[entry_url] != entry_path:
                favorited_data[entry_url] = entry_path
                log.info(
                    f"renaming '{entry_name}' =============> '{favorited_data[entry_url]}'"
                )
        favorited_data = dict(sorted(favorited_data.items(), key=lambda item: item[1]))
        f.seek(0)
        json.dump(obj=favorited_data, fp=f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.truncate()


def map_urls():
    HN_ID_PATTERN = re.compile(f"{re.escape(HN_BASE_URL)}/view/(\\d+)")
    with hn_favorited_json.open("r", encoding="utf-8") as f:
        hn_favorited_data: dict[str, str] = json.load(f)
    with k_favorited_json.open("r", encoding="utf-8") as f:
        k_favorited_data: dict[str, str] = json.load(f)

    reverse_hn = {hn_path: hn_url for hn_url, hn_path in hn_favorited_data.items()}
    reverse_k = {k_path: k_url for k_url, k_path in k_favorited_data.items()}

    left_intersection = {
        k_url: reverse_hn[k_path]
        for k_url, k_path in k_favorited_data.items()
        if k_path in reverse_hn
    }
    right_intersection = {
        hn_url: reverse_k[hn_path]
        for hn_url, hn_path in hn_favorited_data.items()
        if hn_path in reverse_k
    }
    check_dupes(left_intersection)
    check_dupes(right_intersection)

    missing_from_k = {
        hn_path: reverse_hn[hn_path]
        for hn_url, hn_path in hn_favorited_data.items()
        if hn_path not in reverse_k
    }
    missing_from_hn = {
        k_path: reverse_k[k_path]
        for k_url, k_path in k_favorited_data.items()
        if k_path not in reverse_hn
    }
    print_missing(missing_from_k)
    print_missing(missing_from_hn)

    with url_map_json.open("w", encoding="utf-8") as f:
        intersection = dict(
            sorted(
                right_intersection.items(),
                key=lambda item: -int(HN_ID_PATTERN.match(item[0]).group(1)),  # type: ignore
            )
        )
        json.dump(obj=intersection, fp=f, indent=2)


def check_dupes(intersection: dict[str, str]):
    value_counts = collections.Counter(intersection.values())
    dupes = {k: v for k, v in intersection.items() if value_counts[v] != 1}
    if dupes:
        dupes = dict(
            sorted(
                dupes.items(),
                key=lambda item: item[1],
            )
        )
        log.warning(f"duplicate matches found: {json.dumps(dupes, indent=2)}")


def print_missing(missing: dict[str, str]):
    missing = dict(
        sorted(
            missing.items(),
            key=lambda item: item[0],
        )
    )
    if missing:
        log.warning(f"missing entries: {json.dumps(missing, indent=2)}")


def main():
    clean_favorited(hn_favorited_json)
    clean_favorited(k_favorited_json)
    map_urls()


if __name__ == "__main__":
    main()
