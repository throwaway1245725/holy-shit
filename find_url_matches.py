import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from log_setup import log

load_dotenv()

HN_BASE_URL = os.getenv("HN_BASE_URL", "")

parent_dir = Path(__file__).parent

hn_favorited_json = parent_dir / "hn" / "favorited.json"
k_favorited_json = parent_dir / "k" / "favorited.json"

url_map_json = parent_dir / "url_map.json"
with url_map_json.open(mode="r", encoding="utf-8") as f:
    url_map_data: dict[str, str] = json.load(f)


def search_not_downloaded():
    HN_ID_PATTERN = re.compile(f"{re.escape(HN_BASE_URL)}/view/(\\d+)")
    NOT_DOWNLOADED_PATTERN = re.compile(r"\[(?P<artist>.*)\] (?P<title>.*)")
    FAVORITE_PATTERN = re.compile(
        r"^(?P<artist>.*)/(?P<title>.*?)(?: ?\[[^\]]*\]| ?\([^\)]*\))*$"
    )
    with hn_favorited_json.open("r", encoding="utf-8") as f:
        hn_favorited_data: dict[str, str] = json.load(f)
    with k_favorited_json.open("r", encoding="utf-8") as f:
        k_favorited_data: dict[str, str] = json.load(f)

    hn_not_downloaded = {
        hn_url: hn_path[22:]
        for hn_url, hn_path in hn_favorited_data.items()
        if hn_path.startswith("!<not yet downloaded> ")
    }

    def entry_match(not_downloaded: str, favorited: str) -> bool:
        if (nd_m := NOT_DOWNLOADED_PATTERN.match(not_downloaded)) and (
            f_m := FAVORITE_PATTERN.match(favorited)
        ):
            nd_artist = nd_m.group("artist")
            nd_title = nd_m.group("title")
            f_artist = f_m.group("artist")
            f_title = f_m.group("title")
            return nd_artist == f_artist and nd_title == f_title
        else:
            raise Exception("uh")

    hn_matches = {
        hn_url: k_url
        for hn_url, hn_path in hn_not_downloaded.items()
        for k_url, k_path in k_favorited_data.items()
        if not k_path.startswith("!<not yet downloaded> ")
        and entry_match(hn_path, k_path)
    }

    hn_match_check = {
        hn_favorited_data[hn_url][22:]: k_favorited_data[k_url]
        for hn_url, k_url in hn_matches.items()
    }
    print(json.dumps(hn_match_check, indent=2, sort_keys=True))

    new_url_map = {**hn_matches, **url_map_data}

    with url_map_json.open("w", encoding="utf-8") as f:
        new_data = dict(
            sorted(
                new_url_map.items(),
                key=lambda item: -int(HN_ID_PATTERN.match(item[0]).group(1)),  # type: ignore
            )
        )
        json.dump(obj=new_data, fp=f, indent=2)
        f.write("\n")


def main():
    search_not_downloaded()


if __name__ == "__main__":
    main()
