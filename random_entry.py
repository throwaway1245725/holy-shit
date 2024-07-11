import json
import os
import random
import webbrowser
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv

load_dotenv()

VIVALDI_PATH = os.getenv("VIVALDI_PATH")

vivaldi_vpn = webbrowser.get(VIVALDI_PATH)

index_json = Path(__file__).parent / "index.json"

with index_json.open(mode="r", encoding="utf-8") as f:
    index_data: Dict[str, Dict[str, str]] = json.load(f)

all_urls = [
    url for _artist, entries in index_data.items() for _entry, url in entries.items()
]
vivaldi_vpn.open_new_tab(random.choice(all_urls))
