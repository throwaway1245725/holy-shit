import re
from pathlib import Path

p = re.compile(r".*p(\d{3}).*")
for i in Path.cwd().iterdir():
    m = p.match(i.stem)
    if m:
        print(i.with_name(f"{m.group(1)}{i.suffix}"))
        # i.rename(i.with_name(f"{m.group(1)}{i.suffix}"))
