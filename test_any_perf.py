import time
from pathlib import Path

Path("dummy_tests").mkdir(exist_ok=True)
for i in range(100):
    Path(f"dummy_tests/dir_{i}").mkdir(exist_ok=True)
    for j in range(100):
        Path(f"dummy_tests/dir_{i}/test_{j}.py").touch()

start = time.time()
for _ in range(10):
    bool(list(Path("dummy_tests").glob("**/*.py")))
t1 = time.time() - start

start = time.time()
for _ in range(10):
    any(Path("dummy_tests").glob("**/*.py"))
t2 = time.time() - start

print(f"list(): {t1:.4f}s")
print(f"any(): {t2:.4f}s")

import shutil
shutil.rmtree("dummy_tests")
