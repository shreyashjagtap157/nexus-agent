1. **Optimize `src/nexus_agent/__main__.py`**:
   - We will inject `import itertools` and replace the greedy `[str(f) for f in Path.cwd().rglob("*.py")][:20]` with `[str(f) for f in itertools.islice(Path.cwd().rglob("*.py"), 20)]`. Wait, the prompt says "When optimizing Python hot loops involving file traversals, use `itertools.islice` on `pathlib.rglob()` for safety and lazy evaluation, unless explicitly asked to rebuild `rglob`. Custom `os.scandir` implementations can miss path separators and modify expected `rglob` behavior." And also "When replacing `pathlib.Path.rglob()` with `os.scandir()` for performance optimizations...". But wait! Memory specifically said: "When optimizing Python hot loops involving file traversals, use `itertools.islice` on `pathlib.rglob()` for safety and lazy evaluation, unless explicitly asked to rebuild `rglob`. Custom `os.scandir` implementations can miss path separators and modify expected `rglob` behavior."

   I'll use `itertools.islice` with `rglob` instead of writing custom `scandir`.

2. **Optimize `src/nexus_agent/cli/commands/session_mixin.py`**:
   - I'll replace `[str(f) for f in self.workspace.rglob("*.py")][:20]` with `[str(f) for f in itertools.islice(self.workspace.rglob("*.py"), 20)]`. Make sure `import itertools` is available.

3. **Format, Lint, Test**:
   - Run `ruff format src/nexus_agent/__main__.py src/nexus_agent/cli/commands/session_mixin.py`.
   - Run `ruff check src/nexus_agent/__main__.py src/nexus_agent/cli/commands/session_mixin.py --fix`.
   - Run `python -m pytest tests/`.

4. **Journal Entry**:
   - Add journal entry to `.jules/bolt.md` reflecting on how list comprehensions over generators force full evaluation, and using `itertools.islice` avoids it for massive speedup.

5. **Submit PR**:
   - Add the pre-commit step via `pre_commit_instructions`.
   - PR Title: `⚡ Bolt: [performance improvement] Lazy evaluate rglob with itertools.islice`
   - PR Description containing What, Why, Impact, and Measurement.
