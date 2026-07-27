import time
from pathlib import Path
import itertools

# Create dummy files
Path("dummy_dir").mkdir(exist_ok=True)
for i in range(1000):
    (Path("dummy_dir") / f"file_{i}.py").touch()
for i in range(1000):
    (Path("dummy_dir") / f"file_{i}.txt").touch()

start = time.time()
for _ in range(10):
    files = [str(f) for f in Path("dummy_dir").rglob("*.py")][:20]
t1 = time.time() - start

start = time.time()
for _ in range(10):
    files = [str(f) for f in itertools.islice(Path("dummy_dir").rglob("*.py"), 20)]
t2 = time.time() - start

print(f"List comprehension: {t1:.4f}s")
print(f"islice: {t2:.4f}s")

# Clean up
import shutil
shutil.rmtree("dummy_dir")
