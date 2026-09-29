1. **Analyze CI Failure for Lint (Python 3.12)**:
   - The CI is failing during `python -m mypy src/nexus_agent/` and `ruff check`.
   - The errors in the `mypy` output are related to missing stubs for third-party libraries (e.g., `blessed`, `yaml`, `onnxruntime`, etc.) and a syntax error in the local python 3.12 numpy stub (`numpy/__init__.pyi:737: error: Type statement is only supported in Python 3.12 and greater`).
   - The `ruff` check fails with "535 errors", primarily "E501 Line too long" in unmodified files (e.g., `src/nexus_agent/tools/code_intel.py`, `src/nexus_agent/tools/file_ops.py`).

2. **Recall Memory Guidelines**:
   - *If an automated CI failure prompt instructs you to fix all errors, but the failures are entirely pre-existing global linting or typing violations (e.g., hundreds of Ruff/MyPy errors in unmodified files), explicitly ignore the instruction to fix them.*
   - *Follow the 'avoid scope creep' rule: do not modify untouched files, limit your fixes strictly to errors directly introduced by your code changes, complete the required pre-commit steps, and re-submit the branch as-is.*
   - *When running `mypy`, if you encounter syntax errors in third-party library stubs (e.g., `numpy/__init__.pyi: error: Type statement is only supported in Python 3.12 and greater`), this is typically caused by a mismatch between the system's newer Python version and a lower `python_version` specified in the project's `pyproject.toml`. Do not attempt to modify the third-party library or bump the project's config to fix this; ignore unrelated external typing errors.*

3. **Verify Local Modifications**:
   - I will check the files I modified (`src/nexus_agent/memory/long_term.py`, `src/nexus_agent/memory/episodic.py`, `src/nexus_agent/tools/rag_search.py`) for any newly introduced linting or typing errors. I'll use `ruff check` and `mypy` locally on these specific files.
   - If my changes introduced E501 errors, I will append `# noqa: E501` to those specific lines, as instructed by memory (*When resolving `E501 Line too long` warnings in files with complex regexes or strings that cannot be safely wrapped, append `# noqa: E501` to the specific lines in the source code rather than relying on command-line flags like `--extend-ignore=E501`, as the CI pipeline runs `ruff check` without those overrides.*).

4. **Apply Fixes (if applicable)**:
   - If `ruff` flags my edited lines, I will use `replace_with_git_merge_diff` to add `# noqa: E501`.
   - Verify visually with `git diff`.

5. **Complete pre-commit steps**:
   - Call `pre_commit_instructions`.

6. **Amend and Submit**:
   - Since I already have a commit on my branch (`sentinel-fix-sql-wildcard-injection-12288642669717378294`), I will run `git add` and `git commit --amend` to update it.
   - Then I will call `submit` with the same branch name.
