## 2024-06-10 - Sandbox Regex Precompilation
**Learning:** The `Sandbox.classify_risk` method is invoked for every command executed. Previously it compiled several regex patterns on the fly (via `re.search`/`re.match` strings) inside a loop. This caused significant overhead due to Python regex cache misses under heavy load.
**Action:** When a class takes configuration options that contain regex string patterns meant to be checked frequently, compile the `re.Pattern` objects during `__init__` and use `.search()`/`.match()` directly on the hot path.
