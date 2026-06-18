from pathlib import Path
from src.nexus_agent.utils.fs import fast_rglob
import time

start_rglob = time.time()
paths_rglob = [str(f) for f in Path.cwd().rglob("*.py")][:20]
end_rglob = time.time()

start_fast = time.time()
paths_fast = list(fast_rglob(Path.cwd(), "*.py"))[:20]
end_fast = time.time()

print(f"rglob time: {end_rglob - start_rglob:.4f}s")
print(f"fast_rglob time: {end_fast - start_fast:.4f}s")
print(f"rglob count: {len(paths_rglob)}")
print(f"fast_rglob count: {len(paths_fast)}")
