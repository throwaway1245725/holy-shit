import json
from pathlib import Path

from tinydb import TinyDB

db = TinyDB("db.json", indent=2, sort_keys=True)
data_dir = Path.cwd() / "data"


def fetch_metadata(json_path: Path) -> dict:
    with json_path.open(encoding="utf-8") as f:
        return {**json.load(f), "json_path": json_path.relative_to(data_dir).as_posix()}


all_metadata_files = list(data_dir.glob("**/metadata.json"))
if len(db) != len(all_metadata_files):
    db.insert_multiple(map(fetch_metadata, all_metadata_files))
print("oh")
