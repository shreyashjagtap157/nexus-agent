"""Agent slash commands — /mode, /effort, /goal, /plan, /build, /debate, etc.

Extracted from the monolithic command_dispatcher.py.
"""

from __future__ import annotations

import subprocess
import time

from nexus_agent.core.config import save_config


class AgentCommandsMixin:
    """Mixin providing agent-control slash command handlers."""

    def _cmd_mode(self, args: str):
        if args:
            try:
                from nexus_agent.core.agent import AgentMode
                mode = AgentMode(args.lower())
                self._current_mode = mode
                if self._agent:
                    self._agent.mode = mode
                self.r.system_message(f"Mode: {mode.value.upper()}")
            except ValueError:
                self.r.error(f"Invalid mode: {args} (auto|plan|build|review)")
        else:
            self.r.system_message(f"Mode: {self._current_mode.value.upper()}")

    def _cmd_effort(self, args: str):
        valid = ("low", "medium", "high", "xhigh", "max")
        labels = valid

        if args.lower() in valid:
            lvl = args.lower()
            self._config.setdefault("agent", {})["effort_level"] = lvl
            if self._agent:
                self._agent.effort_level = lvl
                from nexus_agent.core.agent import AgentLoop
                ecfg = AgentLoop.EFFORT_CONFIG.get(lvl, AgentLoop.EFFORT_CONFIG["medium"])
                self._agent.max_iterations = ecfg["max_iterations"]
                self._agent.temperature = ecfg["temperature"]
                self._agent.max_tokens = ecfg["max_tokens"]
                self._agent._reflection_enabled = ecfg["reflection"]
            self.r.system_message(f"Effort set to {lvl}")
            save_config(self._config, self.config_path)
            return

        current = self._config.get("agent", {}).get("effort_level", "medium").lower()
        idx = valid.index(current) if current in valid else 1

        self._render_effort_selector(valid, labels, idx)

        while True:
            if not self._kbhit():
                time.sleep(0.02)
                continue
            ch = self._read_byte()
            if ch == b"\xe0":
                ext = self._read_byte()
                if ext == b"K":
                    idx = max(0, idx - 1)
                    self._render_effort_selector(valid, labels, idx)
                elif ext == b"M":
                    idx = min(len(valid) - 1, idx + 1)
                    self._render_effort_selector(valid, labels, idx)
            elif ch == b"\r":
                self._clear_selector()
                lvl = valid[idx]
                self._config.setdefault("agent", {})["effort_level"] = lvl
                if self._agent:
                    self._agent.effort_level = lvl
                    from nexus_agent.core.agent import AgentLoop
                    ecfg = AgentLoop.EFFORT_CONFIG.get(lvl, AgentLoop.EFFORT_CONFIG["medium"])
                    self._agent.max_iterations = ecfg["max_iterations"]
                    self._agent.temperature = ecfg["temperature"]
                    self._agent.max_tokens = ecfg["max_tokens"]
                    self._agent._reflection_enabled = ecfg["reflection"]
                self.r.system_message(f"Effort set to {lvl}")
                save_config(self._config, self.config_path)
                self._refresh_status()
                return
            elif ch in (b"\x1b", b"\x03"):
                self._clear_selector()
                self.r.system_message("Cancelled")
                return

    def _render_effort_selector(self, levels: tuple, labels: tuple, idx: int):
        EFFORT_COLORS = {"low": "32", "medium": "36", "high": "33", "xhigh": "35", "max": "31"}
        PAD = 22

        plain_labels = [str(l) for l in labels]
        widths = [len(w) for w in plain_labels]
        gap = 4
        total_w = sum(widths) + gap * (len(widths) - 1)

        cumulative = 0
        centers = []
        for w in widths:
            centers.append(cumulative + w // 2)
            cumulative += w + gap

        label_parts = []
        for i, lab in enumerate(plain_labels):
            clr = EFFORT_COLORS.get(lab, "0")
            if i == idx:
                label_parts.append(f"\033[1;{clr}m{lab}\033[0m")
            else:
                label_parts.append(f"\033[2;{clr}m{lab}\033[0m")
            if i < len(plain_labels) - 1:
                label_parts.append(" " * gap)

        label_line = " " * PAD + "".join(label_parts)
        ptr_color = EFFORT_COLORS.get(levels[idx], "33")
        marker_line = " " * (PAD + centers[idx]) + f"\033[1;{ptr_color}m\u25b2\033[0m"

        left_w = total_w // 2
        right_w = total_w - left_w

        import sys as _sys
        lines = [
            "",
            "  Effort",
            "",
            f"{' ' * PAD}Faster{' ' * (left_w - 6)}Smarter",
            f"{' ' * PAD}{'\u2500' * left_w}\u252c{'\u2500' * right_w}",
        ]
        lines.append(marker_line)
        lines.append(label_line)
        lines.append("")
        lines.append("  \033[2m\u2190/\u2192 adjust \xb7 Enter confirm \xb7 Esc cancel\033[0m")

        h = len(lines)
        _sys.stdout.write("\033[1B\033[J")
        _sys.stdout.write("\n".join(lines))
        _sys.stdout.write(f"\033[{h}A")
        _sys.stdout.flush()

    def _clear_selector(self):
        import sys as _sys
        _sys.stdout.write("\033[1B\033[J\033[1A")
        _sys.stdout.flush()

    def _cmd_goal(self, args: str):
        if args:
            self._config.setdefault("agent", {})["goal"] = args
            if self._agent:
                self._agent.goal = args
            self.r.system_message(f"Goal: {args}")
            save_config(self._config, self.config_path)
        else:
            g = self._config.get("agent", {}).get("goal", "")
            self.r.system_message(f"Goal: {g}" if g else "No goal set.")

    def _cmd_sandbox(self, args: str):
        if args in ("safe", "moderate", "dangerous", "blocked"):
            from nexus_agent.core.sandbox import RiskLevel
            level = RiskLevel(args.upper())
            self._config.setdefault("sandbox", {})["default_level"] = args
            self.r.system_message(f"Sandbox: {level.value}")
            save_config(self._config, self.config_path)
        else:
            current = self._config.get("sandbox", {}).get("default_level", "moderate")
            self.r.system_message(f"Sandbox: {current.upper()}  Usage: /sandbox [safe|moderate|dangerous|blocked]")

    def _cmd_context(self, args: str):
        self.console.print()
        self.console.print(self._context.render(self._tokens))
        self.console.print()

    def _cmd_memory(self, args: str):
        if not args:
            self._cmd_memory_help()
            return

        # Route subcommands
        if args.startswith("vector"):
            self._cmd_memory_vector(args[6:].strip())
            return

        if args.startswith("local"):
            mem = self._project_memory
            q = args[5:].strip()
            label = "local"
        elif args.startswith("global"):
            mem = self._memory
            q = args[6:].strip()
            label = "global"
        else:
            q = args
            label = None
            mem = None
        if mem:
            if q:
                results = mem.search(q)
                if results:
                    for r in results[:5]:
                        src = r.get("source", "?")
                        cat = r.get("category", "general")
                        content = r.get("content", "")[:120]
                        src_label = label if label else src
                        self.console.print(f"  [{src_label}:{cat}] [dim]{content}[/dim]")
                else:
                    self.r.system_message(f"No memories found: {q}")
            else:
                self.r.system_message(f"Usage: /memory {label or 'global'} <query>")
        elif label == "local" and not q:
            self.r.system_message("Usage: /memory local <query>")
        elif label == "global" and not q:
            self.r.system_message("Usage: /memory global <query>")
        elif label is None and q:
            results_g = self._memory.search(q) if self._memory else []
            results_l = self._project_memory.search(q) if self._project_memory else []
            seen: set[str] = set()
            combined = []
            for r in results_g + results_l:
                key = r.get("content", "")[:80]
                if key not in seen:
                    seen.add(key)
                    combined.append(r)
            if combined:
                for r in combined[:5]:
                    src = r.get("source", "?")
                    cat = r.get("category", "general")
                    content = r.get("content", "")[:120]
                    self.console.print(f"  [global:{src}:{cat}] [dim]{content}[/dim]")
            else:
                self.r.system_message(f"No memories found: {q}")
        else:
            self.r.system_message("Memory unavailable.")

    def _cmd_memory_help(self):
        """Display available memory subcommands."""
        if self._memory:
            self.console.print("  [bold]Memory subsystems:[/bold]")
            self.console.print("  Working:     Active task scratchpad")
            self.console.print("  Long-term:   Persistent knowledge (SQLite FTS5)")
            self.console.print("  Episodic:    Session history")
            self.console.print("  Profile:     Learned preferences")
            if self._project_memory:
                self.console.print("  Project:     Project-level memory")
            self.console.print("  [bold]Vector:[/bold]     Semantic search (embedding-based)")
            self.console.print()
            self.console.print("  [dim]Usage:[/dim]")
            self.console.print("  [dim]  /memory [global|local] <query>   FTS5 text search[/dim]")
            self.console.print("  [dim]  /memory vector stats             Vector store statistics[/dim]")
            self.console.print("  [dim]  /memory vector query <text>      Semantic similarity search[/dim]")
            self.console.print("  [dim]  /memory vector migrate            Re-embed all FTS5 memories into vector store[/dim]")
            self.console.print("  [dim]  /memory vector download           Download ONNX embedding model[/dim]")
        else:
            self.r.system_message("Memory unavailable.")

    def _get_vector_store(self) -> Any | None:
        """Resolve the VectorStore from global or project memory.

        Set by ``_cmd_memory_vector()`` based on the ``--project`` flag.
        """
        mem = self._project_memory if getattr(self, '_vector_use_project', False) else self._memory
        return getattr(mem, "vector", None) if mem else None

    def _get_memory_manager(self) -> Any | None:
        """Resolve the MemoryManager (global or project).

        Set by ``_cmd_memory_vector()`` based on the ``--project`` flag.
        """
        return self._project_memory if getattr(self, '_vector_use_project', False) else self._memory

    @staticmethod
    def _parse_project_flag_from_args(arg_str: str) -> tuple[bool, str]:
        """Parse ``--project`` / ``-p`` flag from the front of a positional arg string.

        Used by subcommand handlers that accept positional args to support
        the ``<subcmd> --project <arg>`` syntax (e.g. ``filter --project <cat>``,
        ``delete --project <id>``, ``query --project <text>``).

        Returns ``(flag_found, remaining_arg)`` where ``flag_found`` tells the
        caller whether to set ``self._vector_use_project = True``.

        Example::

            found, rest = self._parse_project_flag_from_args("--project config")
            # found=True, rest="config"
        """
        if not arg_str:
            return False, arg_str
        if arg_str.startswith("--project") or arg_str.startswith("-p"):
            for prefix in ("--project ", "--project", "-p ", "-p"):
                if arg_str.startswith(prefix):
                    return True, arg_str[len(prefix):].lstrip()
        return False, arg_str

    def _cmd_memory_vector(self, args: str):
        """Handle /memory vector [--project] [stats|query|migrate|...]."""
        self._vector_use_project = False

        # Parse --project / -p flag from the front of args
        stripped = args.lstrip()
        if stripped.startswith("--project") or stripped.startswith("-p"):
            self._vector_use_project = True
            for prefix in ("--project ", "--project", "-p ", "-p"):
                if stripped.startswith(prefix):
                    stripped = stripped[len(prefix):].lstrip()
                    break

        if not stripped:
            label = "project" if self._vector_use_project else "global"
            self.r.system_message(f"Usage: /memory vector [--project] stats | query <text> | list [N] | filter <category> | migrate | download | delete <entry_id> | clear | rebuild")
            return

        parts = stripped.split(maxsplit=1)
        subcmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if subcmd == "stats":
            self._cmd_memory_vector_stats(rest)
        elif subcmd == "query":
            self._cmd_memory_vector_query(rest)
        elif subcmd == "download":
            self._cmd_memory_vector_download()
        elif subcmd == "migrate":
            self._cmd_memory_vector_migrate()
        elif subcmd == "delete" and rest:
            self._cmd_memory_vector_delete(rest)
        elif subcmd == "clear":
            self._cmd_memory_vector_clear()
        elif subcmd == "rebuild":
            self._cmd_memory_vector_rebuild()
        elif subcmd == "list":
            self._cmd_memory_vector_list(rest)
        elif subcmd == "filter" and rest:
            self._cmd_memory_vector_filter(rest)
        elif subcmd == "categories":
            self._cmd_memory_vector_categories()
        else:
            self.r.system_message("Usage: /memory vector stats | query <text> | list [N] | filter <category> | categories | migrate | download | delete <entry_id> | clear | rebuild")

    def _cmd_memory_vector_stats(self, args: str = ""):
        """Show vector store statistics.

        Supports ``--project`` / ``-p`` flag after the subcommand:
        ``/memory vector stats --project``
        """
        # Parse --project / -p flag from remaining args (supports ``stats --project``)
        if args:
            found, _ = self._parse_project_flag_from_args(args.strip())
            if found:
                self._vector_use_project = True
        vs = self._get_vector_store()
        if vs is None:
            self.r.system_message("Vector store is not available. Enable it in memory config.")
            return

        try:
            engine = getattr(vs, "_engine", None)
            mode = engine.mode if engine else "N/A"
            dims = engine.dimensions if engine else "?"
            count = vs.count()
            model_dir = str(getattr(engine, "_model_dir", "")) if engine else ""

            from rich.table import Table
            table = Table(title="Vector Store", show_header=False, box=None, padding=(0, 2))
            table.add_row("  [bold]Engine mode[/bold]", f"[cyan]{mode}[/cyan]")
            table.add_row("  [bold]Dimensions[/bold]", f"{dims}")
            table.add_row("  [bold]Stored entries[/bold]", f"[green]{count}[/green]")
            table.add_row("  [bold]Model directory[/bold]", f"[dim]{model_dir or '(built-in)'}[/dim]")
            label = "project" if getattr(self, '_vector_use_project', False) else "global"
            table.add_row("  [bold]Memory scope[/bold]", f"[cyan]{label}[/cyan]")
            self.console.print()
            self.console.print(table)
            self.console.print()

            # Show available models if ONNX mode
            if mode == "onnx" and engine:
                self.console.print("  [dim]✓ ONNX embedding model loaded and ready[/dim]")
            elif mode == "ngram":
                self.console.print("  [dim]ℹ Using ngram fallback — run /memory vector download for ONNX model[/dim]")
        except Exception as exc:
            self.r.error(f"Failed to get vector store stats: {exc}")

    def _cmd_memory_vector_list(self, args: str):
        """List vector entries with IDs, categories, and content previews.

        Supports ``--project`` / ``-p`` flag before the count:
        ``/memory vector list --project N``

        Optional: ``/memory vector list N``  — show N entries (default 20).
        """
        # Parse --project / -p flag (supports ``list --project N``)
        found, args = self._parse_project_flag_from_args(args.strip())
        if found:
            self._vector_use_project = True

        vs = self._get_vector_store()
        if vs is None:
            self.r.system_message("Vector store is not available.")
            return

        try:
            total = vs.count()
            if total == 0:
                self.r.system_message("Vector store is empty. Run /memory vector migrate to populate from FTS5.")
                return

            show = 20
            if args.strip().isdigit():
                show = int(args.strip())

            entries = vs.list_all(limit=show)
            label = "project" if getattr(self, '_vector_use_project', False) else "global"

            self.console.print()
            self.console.print(f"  [bold]Vector store ({label}):[/bold] [green]{total}[/green] total entries, showing [cyan]{min(show, len(entries))}[/cyan]")
            self.console.print()

            from rich.table import Table
            table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
            table.add_column("#", style="dim", width=4)
            table.add_column("ID", style="dim", width=12, no_wrap=True)
            table.add_column("Category", width=14)
            table.add_column("Content preview", width=70)
            table.add_column("Updated", style="dim", width=12)

            for i, e in enumerate(entries, 1):
                eid = e.get("entry_id", "")[:12]
                cat = e.get("category", "general")
                content = e.get("content", "")[:80]
                updated = e.get("updated_at", 0)
                if updated:
                    import datetime
                    updated_str = datetime.datetime.fromtimestamp(updated).strftime("%H:%M %m-%d")
                else:
                    updated_str = ""
                table.add_row(str(i), eid, f"[{cat}]", content[:80], updated_str)

            self.console.print(table)
            self.console.print()
            self.console.print(f"  [dim]Usage: /memory vector list N  — show N entries (default 20)[/dim]")
        except Exception as exc:
            self.r.error(f"List failed: {exc}")

    def _cmd_memory_vector_categories(self):
        """List all unique categories with entry counts."""
        vs = self._get_vector_store()
        if vs is None:
            self.r.system_message("Vector store is not available.")
            return

        try:
            cats = vs.categories()
            if not cats:
                self.r.system_message("Vector store is empty — no categories to show.")
                return

            total = sum(c["count"] for c in cats)
            label = "project" if getattr(self, '_vector_use_project', False) else "global"

            self.console.print()
            self.console.print(f"  [bold]Categories ({label}):[/bold] [green]{len(cats)}[/green] unique, [cyan]{total}[/cyan] total entries")
            self.console.print()

            from rich.table import Table
            table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
            table.add_column("#", style="dim", width=4)
            table.add_column("Category", width=20)
            table.add_column("Entries", style="green", width=8)
            table.add_column("Distribution", width=30)

            max_count = max(c["count"] for c in cats) if cats else 1
            for i, cat in enumerate(cats, 1):
                name = cat["category"]
                count = cat["count"]
                bar_len = int((count / max_count) * 25)
                bar = "█" * bar_len + "░" * (25 - bar_len)
                pct = int((count / total) * 100)
                table.add_row(str(i), name, str(count), f"{bar} {pct}%")

            self.console.print(table)
            self.console.print()
        except Exception as exc:
            self.r.error(f"Categories failed: {exc}")

    def _cmd_memory_vector_filter(self, category: str):
        """List vector entries in a specific category.

        Supports ``--project`` / ``-p`` flag before the category name:
        ``/memory vector filter --project <category>``
        """
        try:
            category = category.strip()
            if not category:
                self.r.system_message("Usage: /memory vector filter <category>")
                return

            # Parse --project / -p flag (supports ``filter --project <cat>``
            # in addition to the standard ``--project filter <cat>``)
            found, category = self._parse_project_flag_from_args(category)
            if found:
                self._vector_use_project = True
                if not category:
                    self.r.system_message("Usage: /memory vector filter [--project] <category>")
                    return

            vs = self._get_vector_store()
            if vs is None:
                self.r.system_message("Vector store is not available.")
                return

            entries = vs.list_all(category=category)
            if not entries:
                self.r.system_message(f"No entries in category: {category}")
                return

            label = "project" if getattr(self, '_vector_use_project', False) else "global"
            self.console.print()
            self.console.print(f"  [bold]Category ({label}):[/bold] [cyan]{category}[/cyan]  [dim]({len(entries)} entries)[/dim]")
            self.console.print()

            from rich.table import Table
            table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
            table.add_column("#", style="dim", width=4)
            table.add_column("ID", style="dim", width=12, no_wrap=True)
            table.add_column("Content preview", width=80)
            table.add_column("Updated", style="dim", width=12)

            for i, e in enumerate(entries, 1):
                eid = e.get("entry_id", "")[:12]
                content = e.get("content", "")[:80]
                updated = e.get("updated_at", 0)
                if updated:
                    import datetime
                    updated_str = datetime.datetime.fromtimestamp(updated).strftime("%H:%M %m-%d")
                else:
                    updated_str = ""
                table.add_row(str(i), eid, content[:80], updated_str)

            self.console.print(table)
            self.console.print()
            self.console.print(f"  [dim]Usage: /memory vector filter <category>  — filter by category[/dim]")
        except Exception as exc:
            self.r.error(f"Filter failed: {exc}")

    def _cmd_memory_vector_rebuild(self):
        """Recompute all vector store embeddings from stored content.

        Useful after upgrading the embedding model or engine.
        """
        vs = self._get_vector_store()
        if vs is None:
            self.r.system_message("Vector store is not available.")
            return

        try:
            before = vs.count()
            if before == 0:
                self.r.system_message("Vector store is empty — nothing to rebuild. Run /memory vector migrate to populate from FTS5.")
                return

            self.r.show_spinner("Rebuilding vector embeddings")
            count = vs.rebuild()
            self.r.hide_spinner()
            engine_mode = getattr(getattr(vs, "_engine", None), "mode", "?")
            label = "project" if getattr(self, '_vector_use_project', False) else "global"
            self.r.system_message(f"Rebuilt {count} embeddings ({label}) using {engine_mode} engine.")
        except Exception as exc:
            self.r.hide_spinner()
            self.r.error(f"Rebuild failed: {exc}")

    def _cmd_memory_vector_clear(self):
        """Wipe all vector embeddings while keeping FTS5 memories intact."""
        vs = self._get_vector_store()
        if vs is None:
            self.r.system_message("Vector store is not available.")
            return

        try:
            before = vs.count()
            if before == 0:
                self.r.system_message("Vector store is already empty.")
                return

            deleted = vs.clear()
            label = "project" if getattr(self, '_vector_use_project', False) else "global"
            self.r.system_message(f"Cleared {deleted} vector embeddings ({label}). FTS5 memories untouched. Run /memory vector migrate to re-populate.")
        except Exception as exc:
            self.r.error(f"Clear failed: {exc}")

    def _cmd_memory_vector_delete(self, entry_id: str):
        """Delete a specific vector entry by ID.

        Supports ``--project`` / ``-p`` flag before the entry ID:
        ``/memory vector delete --project <entry_id>``
        """
        entry_id = entry_id.strip()
        if not entry_id:
            self.r.system_message("Usage: /memory vector delete <entry_id>")
            return

        # Parse --project / -p flag (supports ``delete --project <id>``)
        found, entry_id = self._parse_project_flag_from_args(entry_id)
        if found:
            self._vector_use_project = True
            if not entry_id:
                self.r.system_message("Usage: /memory vector delete [--project] <entry_id>")
                return

        vs = self._get_vector_store()
        if vs is None:
            self.r.system_message("Vector store is not available.")
            return

        try:
            # Look it up first so we can show what's being deleted
            existing = vs.get(entry_id)
            if existing is None:
                self.r.system_message(f"No vector entry found: {entry_id}")
                return

            ok = vs.delete(entry_id)
            if ok:
                preview = existing.get("content", "")[:80]
                cat = existing.get("category", "general")
                label = "project" if getattr(self, '_vector_use_project', False) else "global"
                self.r.system_message(f"Deleted vector entry ({label}) [{cat}] {preview}...")
            else:
                self.r.error(f"Failed to delete entry: {entry_id}")
        except Exception as exc:
            self.r.error(f"Delete failed: {exc}")

    def _cmd_memory_vector_migrate(self):
        """Migrate all existing FTS5 long-term memories into the vector store.

        Iterates the FTS5 store with pagination, generates embeddings for
        each entry, and stores them in the vector store. Displays progress.
        """
        mem = self._get_memory_manager()
        vs = self._get_vector_store()
        if vs is None or mem is None:
            self.r.system_message("Vector store is not available.")
            return

        try:
            # Get total count from FTS5 store
            stats = mem.long_term.get_stats()
            total = stats.get("total_entries", 0)
            if total == 0:
                self.r.system_message("No long-term memories to migrate.")
                return

            self.console.print()
            self.console.print(f"  [bold]Migrating {total} FTS5 entries → vector store...[/bold]")
            self.console.print()

            migrated = 0
            skipped = 0
            PAGE_SIZE = 50
            offset = 0

            while offset < total:
                entries = mem.long_term.list_all(limit=PAGE_SIZE, offset=offset)
                if not entries:
                    break

                for entry in entries:
                    eid = entry.get("id", "")
                    content = entry.get("content", "")
                    category = entry.get("category", "general")

                    if not content or not content.strip():
                        skipped += 1
                        continue

                    # Check if already in vector store
                    existing = vs.get(eid)
                    if existing:
                        skipped += 1
                        continue

                    vs.store(eid, content, category=category)
                    migrated += 1

                    # Progress line every 10 entries
                    if migrated % 10 == 0 or (migrated + skipped) % PAGE_SIZE == 0:
                        done = migrated + skipped
                        pct = int((done / total) * 100)
                        bar = "█" * (pct // 4) + "░" * (25 - pct // 4)
                        self.console.print(f"    [{bar}] {done}/{total} ({pct}%)  [green]+{migrated}[/green] new  [dim]skipped {skipped}[/dim]")

                offset += PAGE_SIZE

            after_count = vs.count()

            label = "project" if getattr(self, '_vector_use_project', False) else "global"
            self.console.print()
            self.r.system_message(
                f"Migration complete ({label}): {migrated} new embeddings, "
                f"{skipped} skipped (already present or empty), "
                f"total vector entries: {after_count}"
            )
        except Exception as exc:
            self.r.error(f"Migration failed: {exc}")

    def _cmd_memory_vector_download(self):
        """Download the ONNX embedding model for higher-quality vectors."""
        vs = self._get_vector_store()
        engine = getattr(vs, "_engine", None) if vs else None
        if engine is None:
            self.r.system_message("Vector store not available.")
            return

        self.r.show_spinner("Downloading ONNX embedding model from Hugging Face")
        try:
            ok = engine.download_model()
            self.r.hide_spinner()
            if ok:
                self.r.system_message("ONNX embedding model downloaded and loaded. Engine mode: ONNX")
            else:
                self.r.error("Download failed. Check your network connection and try again.")
        except Exception as exc:
            self.r.hide_spinner()
            self.r.error(f"Download failed: {exc}")

    def _cmd_memory_vector_query(self, query: str):
        """Run a semantic similarity query against the vector store.

        Supports ``--project`` / ``-p`` flag before the query text:
        ``/memory vector query --project <text>``
        """
        if not query:
            self.r.system_message("Usage: /memory vector query <text>")
            return

        # Parse --project / -p flag (supports ``query --project <text>``)
        found, query = self._parse_project_flag_from_args(query)
        if found:
            self._vector_use_project = True
            if not query:
                self.r.system_message("Usage: /memory vector query [--project] <text>")
                return

        vs = self._get_vector_store()
        if vs is None:
            self.r.system_message("Vector store is not available.")
            return

        try:
            results = vs.search(query, limit=8, min_score=0.1)
            if not results:
                self.r.system_message(f"No semantic matches found: {query[:60]}")
                return

            label = "project" if getattr(self, '_vector_use_project', False) else "global"
            self.console.print()
            self.console.print(f"  [bold]Semantic search ({label}):[/bold] [dim]{query[:80]}[/dim]")
            self.console.print(f"  [dim]Found {len(results)} results[/dim]")
            self.console.print()

            for i, r in enumerate(results, 1):
                score = r.get("score", 0.0)
                content = r.get("content", "")[:200]
                cat = r.get("category", "general")

                # Color-code the score bar
                pct = int(score * 100)
                bar_len = min(pct, 25)
                bar = "█" * bar_len + "░" * (25 - bar_len)
                if score > 0.7:
                    score_color = "green"
                elif score > 0.4:
                    score_color = "yellow"
                else:
                    score_color = "dim"

                self.console.print(f"  [{score_color}]{bar}[/{score_color}] [{score_color}]{pct:>2}%[/{score_color}]  [{cat}] {content}")

            self.console.print()
            usage = ""
            engine = getattr(vs, "_engine", None)
            if engine:
                usage = f"(embedding: {engine.mode})"
            self.console.print(f"  [dim]Results shown: {len(results)}/8 ({label})  {usage}[/dim]")
        except Exception as exc:
            self.r.error(f"Vector query failed: {exc}")

    def _cmd_reflect(self, args: str):
        if self._agent and self._agent.messages:
            from nexus_agent.llm.base import Role
            last = None
            for m in reversed(self._agent.messages):
                if m.role == Role.ASSISTANT and m.content:
                    last = m.content
                    break
            if last:
                self.r.show_spinner("Critiquing")
                try:
                    critique = self._agent.reflection_engine.evaluate("Last request", last)
                    self.r.hide_spinner()
                    self.console.print()
                    self.console.print(critique.to_feedback_prompt())
                except (ValueError, RuntimeError) as e:
                    self.r.hide_spinner()
                    self.r.error(f"Reflection: {e}")
            else:
                self.r.system_message("No response to critique.")
        else:
            self.r.system_message("No agent active.")

    def _cmd_debate(self, args: str):
        if self._agent:
            from nexus_agent.core.debate import DebateEngine
            self.r.show_spinner("Convening panel")
            try:
                diff = subprocess.run(["git", "diff", "HEAD"], cwd=str(self.workspace), capture_output=True, text=True, timeout=10)
                changes = diff.stdout or ""
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                changes = ""
            if not changes:
                changes = "(no git changes)"
            try:
                engine = DebateEngine(provider=self._agent.provider)
                self.r.hide_spinner()
                verdict = engine.run_debate(code_changes=changes)
                self.r.assistant_message(verdict.consensus_summary + "\n\n" + "\n".join(f"- {r}" for r in verdict.recommendations[:5]))
            except (ValueError, RuntimeError) as e:
                self.r.hide_spinner()
                self.r.error(f"Debate: {e}")

    def _cmd_verify(self, args: str):
        from nexus_agent.core.devops import VerificationPipeline
        self.r.show_spinner("Running verification pipeline")
        try:
            pipeline = VerificationPipeline(workspace=self.workspace)
            report = pipeline.run_full_pipeline()
            self.r.hide_spinner()
            lines = [
                "**Verification Report**",
                f"- Status: {'✅ SUCCESS' if report.success else '❌ FAILURE'}",
                f"- Test framework: {report.test_framework_detected or 'None'}",
                f"- Tests passed: {report.tests_passed}",
                f"- Linters passed: {report.linters_passed}",
            ]
            if report.secrets_found:
                lines.append("- 🔒 Secrets:")
                for s in report.secrets_found:
                    lines.append(f"  - {s.file_path}:{s.line_number} ({s.pattern_name})")
            if report.vulnerabilities_found:
                lines.append("- ⚠️  Vulnerabilities:")
                for v in report.vulnerabilities_found:
                    lines.append(f"  - {v}")
            self.r.assistant_message("\n".join(lines))
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as e:
            self.r.hide_spinner()
            self.r.error(f"Verification: {e}")

    def _cmd_diff(self, args: str):
        target = args or "HEAD"
        try:
            result = subprocess.run(
                ["git", "diff", target],
                cwd=str(self.workspace), capture_output=True, text=True, timeout=15,
            )
            output = result.stdout or result.stderr or "(no diff)"
            if len(output) > 3000:
                output = output[:3000] + f"\n  ... (truncated, {len(output)} total chars)"
            from rich.syntax import Syntax
            self.console.print(Syntax(output, "diff", theme="monokai", word_wrap=True))
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.r.error(f"Diff failed: {e}")

    def _cmd_branch(self, args: str):
        try:
            if args:
                subprocess.run(["git", "checkout", args], cwd=str(self.workspace), capture_output=True, text=True, timeout=10)
            else:
                result = subprocess.run(["git", "branch"], cwd=str(self.workspace), capture_output=True, text=True, timeout=10)
                self.console.print(f"  [dim]{result.stdout.strip()}[/dim]")
                return
            self.r.system_message(f"Switched to branch: {args}")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.r.error(f"Branch: {e}")

    def _cmd_commit(self, args: str):
        if not self._agent:
            self.r.system_message("No agent.")
            return
        from nexus_agent.tools.git_ops import SmartCommitTool
        self.r.show_spinner("Generating commit message")
        try:
            tool = SmartCommitTool(workspace=self.workspace, provider=self._agent.provider)
            msg = tool.execute()
            self.r.hide_spinner()
            self.console.print(f"\n  [dim]{msg}[/dim]\n")
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as e:
            self.r.hide_spinner()
            self.r.error(f"Commit: {e}")

    def _cmd_pr(self, args: str):
        from nexus_agent.tools.git_ops import PRReviewTool
        self.r.show_spinner("Generating PR summary")
        try:
            pr_tool = PRReviewTool(workspace=self.workspace, provider=self._agent.provider if self._agent else None)
            summary = pr_tool.execute()
            self.r.hide_spinner()
            self.r.assistant_message(summary)
        except (ValueError, RuntimeError) as e:
            self.r.hide_spinner()
            self.r.error(f"PR: {e}")

    def _cmd_retry(self, args: str):
        if not self._agent or not self._agent.messages:
            self.r.system_message("Nothing to retry.")
            return
        from nexus_agent.llm.base import Role
        for msg in reversed(self._agent.messages):
            if msg.role == Role.USER and msg.content:
                self.r.system_message("Retrying last user request...")
                self._processing = True
                self._run_agent(msg.content)
                self._processing = False
                return
        self.r.system_message("No user message found to retry.")

    def _cmd_undo(self, args: str):
        try:
            result = subprocess.run(
                ["git", "checkout", "--", "."],
                cwd=str(self.workspace), capture_output=True, text=True, timeout=10,
            )
            self.r.system_message(f"Undone: {result.stdout.strip() or 'working tree cleaned'}")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.r.error(f"Undo: {e}")

    def _cmd_btw(self, args: str):
        """Ask a quick side question (ephemeral — not added to main history)."""
        if not self._agent or not self._engine:
            self.r.system_message("No model loaded.")
            return
        if not args:
            self.r.system_message("Usage: /btw <quick question>")
            return
        try:
            from nexus_agent.core.agent import AgentEventType, AgentMode
            saved_mode = self._agent.mode
            self._agent.mode = AgentMode.PLAN
            self.r.show_spinner("Thinking")
            chunks: list[str] = []
            for event in self._agent.run(args):
                if event.type == AgentEventType.CONTENT_COMPLETE and isinstance(event.data, str):
                    chunks.append(event.data)
                elif event.type == AgentEventType.CONTENT and isinstance(event.data, str):
                    chunks.append(event.data)
                elif event.type == AgentEventType.ERROR:
                    self.r.hide_spinner()
                    self.r.error(f"BTW failed: {event.data}")
                    self._agent.mode = saved_mode
                    return
            self.r.hide_spinner()
            self._agent.mode = saved_mode
            text = "".join(chunks).strip()
            if text:
                from rich.panel import Panel
                self.console.print()
                self.console.print(Panel(text, title="BTW", border_style="dim"))
                self._copied_text = text
        except (ValueError, OSError, RuntimeError) as e:
            self.r.hide_spinner()
            self.r.error(f"BTW failed: {e}")

    def _cmd_fast(self, args: str):
        """Toggle fast mode."""
        if not self._agent:
            self.r.system_message("No active agent.")
            return
        current = getattr(self, "_fast_mode", False)
        self._fast_mode = not current
        if self._fast_mode:
            self._agent.max_iterations = 5
            self._agent.temperature = 0.5
            self.r.system_message("Fast mode: ON (5 it, T=0.5)")
        else:
            self._agent.max_iterations = self._agent._initial_max_iterations
            self._agent.temperature = self._agent._initial_temperature
            self.r.system_message("Fast mode: OFF (restored defaults)")

    def _cmd_plan(self, args: str):
        self._run_agent(f"Plan the implementation for: {args}" if args else "Generate implementation plan for the current task.")

    def _cmd_build(self, args: str):
        self._run_agent("Execute the implementation plan step by step.")

    def _cmd_orchestrate(self, args: str):
        self._run_agent("Orchestrate: plan, approve, execute, verify cycle.")

    def _cmd_autonomous(self, args: str):
        self._run_agent("Run autonomously to achieve the goal.")

    def _cmd_review(self, args: str):
        self._run_agent("Review the current code changes.")

    def _cmd_compact(self, args: str):
        if self._agent:
            self.r.system_message("Compacting conversation…")
            self._agent.compact_history()
            self.r.system_message("Compacted.")
        else:
            self.r.system_message("No agent active.")

    def _cmd_quick(self, args: str):
        self._run_agent(args)
