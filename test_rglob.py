import sys
from pathlib import Path
sys.path.insert(0, str(Path('src').resolve()))
from nexus_agent.utils.fs import iter_all_files

from tempfile import TemporaryDirectory

with TemporaryDirectory() as tmpdir:
    d = Path(tmpdir)
    files = [
        ".hidden/secret.txt",
        "a.txt",
        "build/output.bin",
        "nested/child.txt",
        "node_modules/pkg.json",
        "z.txt",
    ]
    for relative in files:
        path = d / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")

    # Let's inspect the types of paths yielded by rglob vs iter_all_files
    # For rglob:
    rglob_paths = list(d.rglob("*"))
    print("rglob paths:")
    for p in rglob_paths:
        print(f"  {p} - type: {type(p)}")

    print("\niter_all_files paths:")
    scandir_paths = list(iter_all_files(d))
    for p in scandir_paths:
        print(f"  {p} - type: {type(p)}")
