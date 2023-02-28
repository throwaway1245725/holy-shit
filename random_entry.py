import json
import random
import webbrowser
from pathlib import Path
from typing import Dict

vivaldi_vpn = webbrowser.get(
    "C:/Users/big_soup/AppData/Local/Vivaldi VPN/Application/vivaldi.exe %s --incognito"
)

index_json = Path.cwd() / "index.json"

with index_json.open(mode="r", encoding="utf-8") as f:
    index_data: Dict[str, Dict[str, str]] = json.load(f)

all_urls = [
    url for _artist, entries in index_data.items() for _entry, url in entries.items()
]
vivaldi_vpn.open_new_tab(random.choice(all_urls))
