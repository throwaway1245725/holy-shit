import re
from pathlib import Path

p = re.compile(r".*p(\d{3}) \[x3200\].*")
for i in Path.cwd().iterdir():
    m = p.match(i.stem)
    if m:
        print(i.with_name(f"{int(m.group(1)):02}{i.suffix}"))
        # i.rename(i.with_name(f"{int(m.group(1)):02}{i.suffix}"))
