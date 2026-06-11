## 2024-05-23 - Avoid per-line Path operations in tight loops
**Learning:** Checking `file_path.suffix.lower()` inside a line-by-line loop is surprisingly slow because `pathlib.Path.suffix` allocates memory and parses strings on every invocation. When scanning large repositories during RAG indexing, this per-line string operation became a measurable bottleneck, causing unnecessary overhead for every single line in every file.
**Action:** Always pre-compute file metadata (like extension/suffix) outside of line-by-line parsing loops.
