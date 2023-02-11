import re
from pathlib import Path

artist_name_pattern = r"^\[[^\]]*\]"
tags_pattern = r"\{[^\}]*\}$"
koushoku_pattern = r"\(koushoku\.org\)"

data_dir = Path.cwd() / "data"


def clean_name(name: str):
    new_name = re.sub(artist_name_pattern, "", name)
    new_name = re.sub(tags_pattern, "", new_name)
    new_name = re.sub(koushoku_pattern, "", new_name)
    return new_name.strip()


for artist in data_dir.iterdir():
    for entry in artist.iterdir():
        cleaned_name = clean_name(entry.name)
        if entry.name != cleaned_name:
            print(f"{artist.name}/{entry.name} =============> {cleaned_name}")
            entry.rename(entry.with_name(cleaned_name))
