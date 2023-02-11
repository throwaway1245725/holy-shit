import json
from pathlib import Path
from typing import Dict

root_path = Path.cwd()

artists = [
    path
    for path in (root_path / "data").iterdir()
    if path.is_dir() and not path.name.startswith(".")
]

with (root_path / "index.json").open(mode="r", encoding="utf-8") as f:
    index_data: Dict[str, Dict[str, str]] = json.load(f)

for artist in artists:
    if artist.name in index_data:
        dir_entries_set = set(
            entry.name for entry in artist.iterdir() if entry.is_dir()
        )
        data_entries_set = set(index_data[artist.name])
        missing_entries = dir_entries_set - data_entries_set
        if missing_entries:
            for missing_entry in missing_entries:
                index_data[artist.name][missing_entry] = ""
                print(f"added missing entry: {artist.name}/{missing_entry}")

        invalid_entries = data_entries_set - dir_entries_set
        if invalid_entries:
            for invalid_entry in invalid_entries:
                del index_data[artist.name][invalid_entry]
                print(f"deleted invalid entry: {artist.name}/{invalid_entry}")
    else:
        index_data[artist.name] = {entry.name: "" for entry in artist.iterdir()}
        print(
            f"created missing artist {artist.name} with {len(index_data[artist.name])} entries"
        )

with (root_path / "index.json").open(mode="w", encoding="utf-8") as f:
    json.dump(obj=index_data, fp=f, indent=2, ensure_ascii=False, sort_keys=True)

missing_links = sorted(
    (artist, entry)
    for artist, entries in index_data.items()
    for entry, value in entries.items()
    if not value
)
if missing_links:
    print(f"missing links: ")
    for artist, entry in missing_links:
        print(f"{artist}/{entry}")
