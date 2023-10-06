import json
from pathlib import Path

from tinydb import Query, TinyDB

db = TinyDB("db.json", indent=2, ensure_ascii=False, sort_keys=True, encoding="utf-8")
data_dir = Path.cwd() / "data"

# https://tinydb.readthedocs.io/en/latest/usage.html

#
Entry = Query()
# db.search(Entry.title == "")
# db.search(Entry.title.matches("[aZ]*"))
# db.search(Entry.artists.any[""])
# db.search(Entry.tags.any["", ""])


def check_db_file():
    def fetch_metadata(json_path: Path) -> dict:
        with json_path.open(encoding="utf-8") as f:
            return {
                **json.load(f),
                "json_path": json_path.relative_to(data_dir).as_posix(),
            }

    all_metadata_files = list(data_dir.glob("**/metadata.json"))
    if len(db) != len(all_metadata_files):
        db.drop_tables()
        db.insert_multiple(map(fetch_metadata, all_metadata_files))


print("oh")

# check_db_file()
