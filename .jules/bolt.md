## 2024-05-14 - Lazy Evaluation of rglob with itertools.islice

**Learning:** When using generator-based traversal functions like `pathlib.Path.rglob()` to find a limited number of files, combining a list comprehension with slicing (e.g. `[str(f) for f in path.rglob(...)][:limit]`) forces the Python interpreter to greedily exhaust the entire generator into memory before slicing. In large repositories, this causes massive CPU spikes, slows down execution, and risks an Out-Of-Memory (OOM) crash.

**Action:** Always use `itertools.islice()` around the generator directly (e.g. `[str(f) for f in itertools.islice(path.rglob(...), limit)]`) to guarantee lazy consumption of the iterator. This terminates the traversal immediately after the limit is reached, saving significant time and memory.

## 2024-05-14 - Lazy Evaluation of rglob with itertools.islice

**Learning:** When using generator-based traversal functions like `pathlib.Path.rglob()` to find a limited number of files, combining a list comprehension with slicing (e.g. `[str(f) for f in path.rglob(...)][:limit]`) forces the Python interpreter to greedily exhaust the entire generator into memory before slicing. In large repositories, this causes massive CPU spikes, slows down execution, and risks an Out-Of-Memory (OOM) crash.

**Action:** Always use `itertools.islice()` around the generator directly (e.g. `[str(f) for f in itertools.islice(path.rglob(...), limit)]`) to guarantee lazy consumption of the iterator. This terminates the traversal immediately after the limit is reached, saving significant time and memory.
