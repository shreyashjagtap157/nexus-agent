import time
import os
import itertools
from pathlib import Path

def bench_islice_prefix(path, prefix):
    t0 = time.time()
    matches = []
    try:
        for p in itertools.islice(Path(path).rglob(f"*{prefix}*"), 20):
            if p.is_file():
                # We can't really do relative_to perfectly without the loop
                matches.append(str(p))
    except Exception:
        pass
    print(f"islice_prefix: {time.time() - t0}")

bench_islice_prefix('.', 'test')
