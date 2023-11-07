import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Set, Tuple, Union

from log_setup import log

data_dir = Path.cwd() / "data"
downloaded_dir = Path.cwd() / "downloaded"
downloaded_json = Path.cwd() / "downloaded.json"
index_json = Path.cwd() / "index.json"
with index_json.open(mode="r", encoding="utf-8") as f:
    index_data: Dict[str, Dict[str, str]] = json.load(f)
with downloaded_json.open(mode="r", encoding="utf-8") as f:
    downloaded_data: Dict[str, str] = json.load(f)


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
        log.info(f"moving {type}:")
        for new_path, page in paths_to_move_source.items():
            log.info(f"{page.name} =============> {new_path.name}")
            page.rename(new_path)
    else:
        log.info(f"no {type} to move")


def clean_directory_name(name: str):
    ARTIST_NAME_PATTERN = r"^\[[^\]]*\]"
    TAGS_PATTERN = r"\{[^\}]*\}$"
    KOUSHOKU_PATTERN = r"\(koushoku\.org\)|\(ksk\.moe\)"
    new_name = re.sub(ARTIST_NAME_PATTERN, "", name)
    new_name = re.sub(TAGS_PATTERN, "", new_name)
    new_name = re.sub(KOUSHOKU_PATTERN, "", new_name)
    new_name = re.sub("’", "'", new_name)
    new_name = re.sub("？", "", new_name)
    new_name = re.sub("–", "-", new_name)
    return new_name.strip()


def copy_indexed_archives_to_data_dir():
    for artist, entries in index_data.items():
        artist_path = data_dir / artist
        artist_path.mkdir(exist_ok=True)
        for entry, url in entries.items():
            entry_path = artist_path / entry
            if not entry_path.exists():
                cbz_filename = f"{downloaded_data[url]}.cbz"
                source_cbz_path = downloaded_dir / cbz_filename
                dest_cbz_path = artist_path / cbz_filename
                if (
                    not dest_cbz_path.exists()
                    and not (artist_path / downloaded_data[url]).exists()
                ):
                    log.info(f"copying {source_cbz_path} to {dest_cbz_path}")
                    shutil.copy(source_cbz_path, dest_cbz_path)


def unzip_all():
    for artist_path in data_dir.iterdir():
        for archive in (
            archive for archive in artist_path.iterdir() if archive.suffix in [".cbz"]
        ):
            archive_path = archive.with_suffix("")
            archive_path = archive_path.with_name(archive_path.name.strip())
            log.info(f"extracting and deleting {archive.name}")
            with zipfile.ZipFile(archive, "r") as zip:
                zip.extractall(archive_path)
            archive.unlink()


def rename_and_add_entries():
    for artist_path in data_dir.iterdir():
        for source_entry_path in artist_path.iterdir():
            entry_url = next(
                (
                    url
                    for url, filename in downloaded_data.items()
                    if filename.strip() == source_entry_path.name
                ),
                None,
            )
            if entry_url:
                if artist_path.name not in index_data.keys():
                    index_data[artist_path.name] = {}
                dest_entry_name = next(
                    (
                        entry
                        for entry, url in index_data[artist_path.name].items()
                        if url == entry_url
                    ),
                    None,
                )
                if not dest_entry_name:
                    dest_entry_name = clean_directory_name(source_entry_path.name)
                    log.info(
                        f"adding entry to index and favorited: {artist_path.name}/{dest_entry_name}"
                    )
                    index_data[artist_path.name][dest_entry_name] = entry_url
                    with index_json.open("w", encoding="utf-8") as f:
                        json.dump(
                            obj=index_data,
                            fp=f,
                            indent=2,
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        f.write("\n")
                log.info(
                    f"renaming {artist_path.name}/{source_entry_path.name} to {artist_path.name}/{dest_entry_name}"
                )
                source_entry_path.rename(source_entry_path.with_name(dest_entry_name))


def clean_entries():
    log.info("========== cleaning entries ==========")

    entries_to_move_source: Dict[Path, Path] = {}
    conflicts: List[Tuple[Path, Path]] = []

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
        log.info("no entries to move")


def clean_filenames():
    log.info("========== cleaning_filenames ==========")
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
        "irodori_index": re.compile(r"index-(?P<page1>\d+)_1"),
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
        page2: Union[str, None] = None,
        suffix: Union[str, None] = None,
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
        "irodori_index": clean_simple,
        "wtf_is_that": clean_simple,
    }

    def process_entry(entry: Path):
        entry_matches: Set[Tuple[Path, re.Match]] = set()
        matched_pattern_name: Union[str, None] = None

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

        if not matched_pattern_name:
            raise Exception("no cleaner found")
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
        log.info("no pages to move")


def check_multi_entries():
    log.info("========== checking for new multi-entries ==========")
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
        log.warning("new multi-entries found:")
        log.warning(json.dumps(sorted(new_multi_entries), indent=2))
    else:
        log.info("no new multi-entries found")


def check_missing_entries():
    log.info("========== checking for missing entries ==========")
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
        log.warning("missing entries detected:")
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
            log.warning(line)
    else:
        log.info("no missing entries detected")


copy_indexed_archives_to_data_dir()
unzip_all()
rename_and_add_entries()
clean_entries()
clean_filenames()
check_multi_entries()
check_missing_entries()
