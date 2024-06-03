import re
from pathlib import Path

p = re.compile(r"[^\d]+(\d+)")
for i in Path.cwd().iterdir():
    m = p.match(i.stem)
    if m:
        print(i.with_name(f"{int(m.group(1))+1:02}{i.suffix}"))
        # i.rename(i.with_name(f"{int(m.group(1))+1:02}{i.suffix}"))
