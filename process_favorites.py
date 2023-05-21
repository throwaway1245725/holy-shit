import json
import re
import time
from pathlib import Path
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

URL_PATTERN = re.compile(r"https:\/\/ksk\.moe\/view\/(.*)")
N_RESULTS_PATTERN = re.compile(r"Found (.*) result")

index_json = Path.cwd() / "index.json"
favorited_json = Path.cwd() / "favorited.json"

with index_json.open("r", encoding="utf-8") as f:
    index_data: Dict[str, Dict[str, str]] = json.load(f)

entries = (
    (artist, entry, url)
    for artist, entries in index_data.items()
    for entry, url in entries.items()
)


def add_missing_favorites():
    for artist, entry, url in entries:
        with favorited_json.open("r+", encoding="utf-8") as f:
            favorited_data: Dict[str, str] = json.load(f)
            if url in favorited_data.keys():
                # print(f"not adding {artist}/{entry} already in favorites")
                pass
            else:
                print(f"adding {artist}/{entry} to favorites")
                partial_url = URL_PATTERN.match(url).group(1)
                response = requests.post(
                    f"https://ksk.moe/favorite/{partial_url}",
                    headers={
                        "cookie": "refresh=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2ODYzMjcxMzYsImlkIjoiMmVjNWJjMGEtOTY1NS00MTEzLWI5OGMtNDEyODEyZWJmYmQ5In0.pPSAqrnMyUuN7ILXrKfyndWxsIUDeRS3_QqKae6-wrs; session=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2ODQ2OTk3MDAsImlkIjoiODU0OTUwNDEtZjVkNi00ZTZlLWI5YmItOTk0MDBiZDQyYzEwIn0.Akkr7d5jq6phHak2DSwluKT_ojsEStVdj9BFzFrrQvQ; __cf_bm=s6e2lQHKpZSMVgTTGGCLfdtxGKVj_6SLD0Xt0heKySc-1684697901-0-AXX5/0/3M0DFGG4AUSJSkv26pVFuLgo/nRqjWB0zMrztZdaxoUtBsqkfxbqTuiUJuQOH/1MCHhx7dtRHAIMTP+0/GzWVnXyL3wN23j7WBFnJ; zeit=MTY4NDY5OTI2OXxEdi1CQkFFQ180SUFBUkFCRUFBQV8tN19nZ0FDQm5OMGNtbHVad3dLQUFoamMzSm1VMkZzZEFaemRISnBibWNNRWdBUVVXOWxRM0JUVVRaRlFsSXdiMkZQTlFaemRISnBibWNNQmdBRVgyMXpad1p6ZEhKcGJtY01fNk1BXzZCU01rWnpZa2RXZVdWVFFXNVRNMVo1WWpOT01VbEZaR2hrUjBaNVlWTkJkRWxGVW1oamJYUnNZek5SWjFKSFZucGhXRXBzVDJsQ1ZXRkhWV2RSYld4dVNVVktjMWxYVG5KSlJVNTJZa2Q0YkZrelVuQmlNalJuUzBOTmVFMVVWVEJOUXpnMVRsUkJkMDFxWnpSWk1ra3lXWHBCY0VwNVFtOVpXRTFuV1cxV2JHSnBRbmxhVnpGMlpHMVdhMGxIV25saU1qQm5XbTFHTW1JelNuQmtSMVo2fKT_gSZJkYClScWXMRHUET4As4h7szn2LJLRATs1YSO_"
                    },
                )
                if response.status_code != 200:
                    raise Exception("what!?")
                favorited_data[url] = f"{artist}/{entry}"
                # sorting by value
                favorited_data = dict(
                    sorted(favorited_data.items(), key=lambda item: item[1])
                )
                f.seek(0)
                json.dump(obj=favorited_data, fp=f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.truncate()


def find_weirdness():
    with favorited_json.open("r", encoding="utf-8") as f:
        favorited_data: Dict[str, str] = json.load(f)
    urls = set(favorited_data.keys())
    print(f"number of entries in total: {len(urls)}")
    for artist, entries in index_data.items():
        page = requests.get(
            f'https://ksk.moe/favorites?s=artist:"{artist}"',
            headers={
                "cookie": "refresh=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2ODYzMjcxMzYsImlkIjoiMmVjNWJjMGEtOTY1NS00MTEzLWI5OGMtNDEyODEyZWJmYmQ5In0.pPSAqrnMyUuN7ILXrKfyndWxsIUDeRS3_QqKae6-wrs; session=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2ODQ2OTk3MDAsImlkIjoiODU0OTUwNDEtZjVkNi00ZTZlLWI5YmItOTk0MDBiZDQyYzEwIn0.Akkr7d5jq6phHak2DSwluKT_ojsEStVdj9BFzFrrQvQ; __cf_bm=s6e2lQHKpZSMVgTTGGCLfdtxGKVj_6SLD0Xt0heKySc-1684697901-0-AXX5/0/3M0DFGG4AUSJSkv26pVFuLgo/nRqjWB0zMrztZdaxoUtBsqkfxbqTuiUJuQOH/1MCHhx7dtRHAIMTP+0/GzWVnXyL3wN23j7WBFnJ; zeit=MTY4NDY5OTI2OXxEdi1CQkFFQ180SUFBUkFCRUFBQV8tN19nZ0FDQm5OMGNtbHVad3dLQUFoamMzSm1VMkZzZEFaemRISnBibWNNRWdBUVVXOWxRM0JUVVRaRlFsSXdiMkZQTlFaemRISnBibWNNQmdBRVgyMXpad1p6ZEhKcGJtY01fNk1BXzZCU01rWnpZa2RXZVdWVFFXNVRNMVo1WWpOT01VbEZaR2hrUjBaNVlWTkJkRWxGVW1oamJYUnNZek5SWjFKSFZucGhXRXBzVDJsQ1ZXRkhWV2RSYld4dVNVVktjMWxYVG5KSlJVNTJZa2Q0YkZrelVuQmlNalJuUzBOTmVFMVVWVEJOUXpnMVRsUkJkMDFxWnpSWk1ra3lXWHBCY0VwNVFtOVpXRTFuV1cxV2JHSnBRbmxhVnpGMlpHMVdhMGxIV25saU1qQm5XbTFHTW1JelNuQmtSMVo2fKT_gSZJkYClScWXMRHUET4As4h7szn2LJLRATs1YSO_"
            },
        )
        soup = BeautifulSoup(page.text, "html.parser")
        n_results_str = soup.find(id="galleries").header.i.text
        n_results = int(
            N_RESULTS_PATTERN.match(n_results_str).group(1).replace(",", "")
        )
        if n_results != len(entries):
            print(
                f"artist {artist} number of entries mismatch ({n_results} vs {len(entries)})"
            )


add_missing_favorites()
# find_weirdness()
