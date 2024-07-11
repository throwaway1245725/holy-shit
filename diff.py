import json
from pathlib import Path

hn_favorited_json = Path(__file__).parent / "hn" / "favorited.json"
with hn_favorited_json.open(mode="r", encoding="utf-8") as f:
    hn_favorited_data: dict[str, str] = json.load(f)

k_favorited_json = Path(__file__).parent / "k" / "favorited.json"
with k_favorited_json.open(mode="r", encoding="utf-8") as f:
    k_favorited_data: dict[str, str] = json.load(f)

reverse_hn = {hn_path: hn_url for hn_url, hn_path in hn_favorited_data.items()}
reverse_k = {k_path: k_url for k_url, k_path in k_favorited_data.items()}

left_intersection = {
    k_url: reverse_hn[k_path]
    for k_url, k_path in k_favorited_data.items()
    if k_path in reverse_hn
}
right_intersection = {
    hn_url: reverse_k[hn_path]
    for hn_url, hn_path in hn_favorited_data.items()
    if hn_path in reverse_k
}

missing_from_k = {
    hn_path: reverse_hn[hn_path]
    for hn_url, hn_path in hn_favorited_data.items()
    if hn_path not in reverse_k
}
missing_from_hn = {
    k_path: reverse_k[k_path]
    for k_url, k_path in k_favorited_data.items()
    if k_path not in reverse_hn
}
print("missing_from_k")
print(json.dumps(missing_from_k, indent=2))
print("missing_from_hn")
print(json.dumps(missing_from_hn, indent=2))
