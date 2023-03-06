import collections
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

data_dir = Path.cwd() / "data"
index_json = Path.cwd() / "index.json"


def add_rename_path(
    source: Path,
    new_name: str,
    paths_to_move_source: Dict[Path, Path],
    conflicts: List[Tuple[Path, Path]],
):
    new_path = source.with_name(new_name)
    if new_path in paths_to_move_source:
        conflicts.append((paths_to_move_source[new_path], source))
    paths_to_move_source[new_path] = source


def do_move(
    paths_to_move_source: Dict[Path, Path],
    conflicts: List[Tuple[Path, Path]],
    type: str,
):
    if paths_to_move_source:
        if conflicts:
            conflicts_str = "\n".join(
                f"{conflict_a}\n{conflict_b}" for conflict_a, conflict_b in conflicts
            )
            error_msg = f"duplicate destination paths!\n{conflicts_str}"
            raise Exception(error_msg)
        print(f"moving {type}:")
        for new_path, page in paths_to_move_source.items():
            print(f"{page.name} =============> {new_path.name}")
            page.rename(new_path)
    else:
        print(f"no {type} to move")


def clean_entries():
    print("========== cleaning entries ==========")
    ARTIST_NAME_PATTERN = r"^\[[^\]]*\]"
    TAGS_PATTERN = r"\{[^\}]*\}$"
    KOUSHOKU_PATTERN = r"\(koushoku\.org\)|\(ksk\.moe\)"

    entries_to_move_source: Dict[Path, Path] = {}
    conflicts: List[Tuple[Path, Path]] = []

    def clean_directory_name(name: str):
        new_name = re.sub(ARTIST_NAME_PATTERN, "", name)
        new_name = re.sub(TAGS_PATTERN, "", new_name)
        new_name = re.sub(KOUSHOKU_PATTERN, "", new_name)
        new_name = re.sub("’", "'", new_name)
        new_name = re.sub("？", "", new_name)
        new_name = re.sub("–", "-", new_name)
        return new_name.strip()

    for artist in data_dir.iterdir():
        for entry in artist.iterdir():
            cleaned_name = clean_directory_name(entry.name)
            if entry.name != cleaned_name:
                add_rename_path(
                    source=entry,
                    new_name=cleaned_name,
                    paths_to_move_source=entries_to_move_source,
                    conflicts=conflicts,
                )

    if entries_to_move_source:
        do_move(entries_to_move_source, conflicts, "entries")
    else:
        print("no entries to move")


def refresh_index():
    print("========== refreshing index ==========")
    artists = [
        path
        for path in data_dir.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    ]
    with index_json.open(mode="r", encoding="utf-8") as f:
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

    with index_json.open(mode="w", encoding="utf-8") as f:
        json.dump(obj=index_data, fp=f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")

    missing_links = sorted(
        (artist, entry)
        for artist, entries in index_data.items()
        for entry, value in entries.items()
        if not value
    )
    if missing_links:
        print(f"missing links:")
        for artist, entry in missing_links:
            print(f"{artist}/{entry}")

    duplicate_urls = set(
        item
        for item, count in collections.Counter(
            url
            for _artist, entries in index_data.items()
            for _entry, url in entries.items()
            if url
        ).items()
        if count > 1
    )
    if duplicate_urls:
        duplicate_urls_str = "\n".join(
            f"{artist}/{entry}:{url}"
            for artist, entries in index_data.items()
            for entry, url in entries.items()
            if url in duplicate_urls
        )
        print(f"duplicate urls detected: \n{duplicate_urls_str}")

    print("finished refreshing index")


def clean_filenames():
    print("========== cleaning_filenames ==========")
    IMAGE_SUFFIXES = [".jpg", ".jpeg", ".png"]

    PATTERNS = {
        "standard": re.compile(
            r"(?<![^\s])\b(?P<page1>\d+)(?:-(?P<page2>\d+))?(?P<suffix>[a-c])?\b(?![^\s])"
        ),
        "fakku": re.compile(
            r"p(?P<page1>\d+)(?:(?:x(?P<suffix>\d))|(?:-p(?P<page2>\d+)))?"
        ),
        "underscores": re.compile(r"_(?P<page1>\d+)_x3200"),
        "million_zeros": re.compile(r"^[a-zA-Z]+[_-]+(?P<page1>\d+)$"),
        "irodori": re.compile(r"Page_(?P<page1>\d+)_Image_0001"),
        "wtf_is_that": re.compile(r"_3200x_(?P<page1>\d+)$"),
    }

    matches: Dict[str, Set[Tuple[Path, re.Match]]] = {
        key: set() for key in PATTERNS.keys()
    }

    pages_to_move_source: Dict[Path, Path] = {}
    conflicts: List[Tuple[Path, Path]] = []

    def generate_name(
        max_int_length: int,
        file_suffix: str,
        page1: str,
        page2: str = None,
        suffix: str = None,
    ) -> str:
        if page2:
            if suffix:
                return f"{int(page1):0{max_int_length}}-{int(page2):0{max_int_length}}{suffix}{file_suffix}"
            else:
                return f"{int(page1):0{max_int_length}}-{int(page2):0{max_int_length}}{file_suffix}"
        elif suffix:
            return f"{int(page1):0{max_int_length}}{suffix}{file_suffix}"
        else:
            return f"{int(page1):0{max_int_length}}{file_suffix}"

    def get_max_int_len(entry_matches: Set[Tuple[Path, re.Match]]):
        return max(
            2, *(len(m.group("page1").lstrip("0")) for (_page, m) in entry_matches)
        )

    def clean_standard(
        entry_matches: Set[Tuple[Path, re.Match]], is_fakku: bool = False
    ):
        max_int_length = get_max_int_len(entry_matches)

        for page, m in entry_matches:
            suffix = m.group("suffix")
            if suffix and is_fakku:
                suffix = chr(ord("a") + int(suffix) - 1)
            new_name = generate_name(
                max_int_length=max_int_length,
                file_suffix=page.suffix,
                page1=m.group("page1"),
                page2=m.group("page2"),
                suffix=suffix,
            )
            if page.name != new_name:
                nonlocal pages_to_move_source
                nonlocal conflicts
                add_rename_path(
                    source=page,
                    new_name=new_name,
                    paths_to_move_source=pages_to_move_source,
                    conflicts=conflicts,
                )

    def clean_fakku(entry_matches: Set[Tuple[Path, re.Match]]):
        clean_standard(entry_matches, is_fakku=True)

    def clean_simple(entry_matches: Set[Tuple[Path, re.Match]]):
        max_int_length = get_max_int_len(entry_matches)

        for page, m in entry_matches:
            new_name = generate_name(
                max_int_length=max_int_length,
                file_suffix=page.suffix,
                page1=m.group("page1"),
            )
            if page.name != new_name:
                nonlocal pages_to_move_source
                nonlocal conflicts
                add_rename_path(
                    source=page,
                    new_name=new_name,
                    paths_to_move_source=pages_to_move_source,
                    conflicts=conflicts,
                )

    CLEANERS = {
        "standard": clean_standard,
        "fakku": clean_fakku,
        "underscores": clean_simple,
        "million_zeros": clean_simple,
        "irodori": clean_simple,
        "wtf_is_that": clean_simple,
    }

    def process_entry(entry: Path):
        entry_matches: Set[Tuple[Path, re.Match]] = set()
        matched_pattern_name: str = None

        def check_match(pattern_name: str, page: Path):
            nonlocal matches
            nonlocal entry_matches
            nonlocal matched_pattern_name
            if m := list(PATTERNS[pattern_name].finditer(page.stem)):
                matches[pattern_name].add((page, m[-1]))
                if not matched_pattern_name:
                    matched_pattern_name = pattern_name
                if matched_pattern_name and matched_pattern_name != pattern_name:
                    raise Exception("what even")
                entry_matches.add((page, m[-1]))

        pages = [page for page in entry.iterdir() if page.suffix in IMAGE_SUFFIXES]
        for page in pages:
            for pattern_name in PATTERNS.keys():
                check_match(pattern_name, page)

        CLEANERS[matched_pattern_name](entry_matches)

    for artist in data_dir.iterdir():
        for entry in artist.iterdir():
            sub_entries = [
                sub_entry for sub_entry in entry.iterdir() if sub_entry.is_dir()
            ]
            if sub_entries:
                for sub_entry in sub_entries:
                    process_entry(sub_entry)
            else:
                process_entry(entry)

    if intersection := set.intersection(
        *(set(page for (page, _m) in match_set) for match_set in matches.values())
    ):
        raise Exception(f"a page matched multiple patterns: {intersection}")

    if pages_to_move_source:
        do_move(pages_to_move_source, conflicts, "pages")
    else:
        print("no pages to move")


def check_multi_entries():
    print("========== checking for new multi-entries ==========")
    multi_entries_json = Path.cwd() / "multi_entries.json"
    with multi_entries_json.open("r") as f:
        confirmed_multi_entries = set(json.load(f))
    existing_multi_entries = set(
        str(entry.relative_to(data_dir))
        for artist in data_dir.iterdir()
        for entry in artist.iterdir()
        if any(sub_entry.is_dir() for sub_entry in entry.iterdir())
    )
    new_multi_entries = existing_multi_entries - confirmed_multi_entries
    if new_multi_entries:
        print("new multi-entries found:")
        print(json.dumps(sorted(new_multi_entries), indent=2))
    else:
        print("no new multi-entries found")


def check_missing_entries():
    print("========== checking for missing entries ==========")
    with index_json.open(mode="r", encoding="utf-8") as f:
        index_data: Dict[str, Dict[str, str]] = json.load(f)
    index_entries = set(
        f"{artist}/{entry}"
        for artist, entries in index_data.items()
        for entry, _url in entries.items()
    )
    actual_entries = set(
        f"{artist.name}/{entry.name}"
        for artist in data_dir.iterdir()
        for entry in artist.iterdir()
    )
    missing_entries = index_entries - actual_entries
    if missing_entries:
        print("missing entries detected:")
        ARTIST_ENTRY_PATTERN = re.compile(r"(?P<artist>.*)\/(?P<entry>.*)")

        def get_entry_url(entry: str) -> str:
            m = ARTIST_ENTRY_PATTERN.match(entry)
            if m and "artist" in m.groupdict() and "entry" in m.groupdict():
                return index_data[m.group("artist")][m.group("entry")]
            else:
                raise Exception("what in the??")

        missing_entries_with_url = sorted(
            f"{missing_entry}: {get_entry_url(missing_entry)}"
            for missing_entry in missing_entries
        )
        for line in missing_entries_with_url:
            print(line)
    else:
        print("no missing entries detected")


def main():
    clean_entries()
    refresh_index()
    clean_filenames()
    check_multi_entries()
    check_missing_entries()


if __name__ == "__main__":
    main()
