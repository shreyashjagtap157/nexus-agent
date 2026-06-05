"""Tools slash commands — /search, /index, /browser, /mcp, /skill."""

from __future__ import annotations

from nexus_agent.cli.commands._base import BaseCommands
from nexus_agent.core.config import save_config


class ToolsCommands(BaseCommands):
    """Mixin providing tool-related slash command handlers."""


    def _cmd_search(self, args: str):
        if not args:
            self.r.system_message("Usage: /search <query>")
            return
        self.r.show_spinner("Searching workspace")
        try:
            from nexus_agent.tools.rag_search import RepositoryRAGTool
            tool = RepositoryRAGTool(self.workspace)
            results = tool.execute(query=args, max_results=8)
            self.r.hide_spinner()
            if isinstance(results, str):
                self.r.assistant_message(results[:2000])
            elif results:
                for r in results[:8]:
                    path = r.get("file_path", r.get("path", "?"))
                    snippet = r.get("content", r.get("snippet", ""))[:120]
                    self.console.print(f"  [cyan]{path}[/cyan]")
                    self.console.print(f"  [dim]{snippet}[/dim]\n")
            else:
                self.r.system_message(f"No results for: {args}")
        except (ValueError, RuntimeError, OSError) as e:
            self.r.hide_spinner()
            self.r.error(f"Search: {e}")


    def _cmd_index(self, args: str):
        self.r.show_spinner("Indexing workspace")
        try:
            from nexus_agent.tools.rag_search import RepositoryRAGTool
            tool = RepositoryRAGTool(self.workspace)
            result = tool.execute(action="index_all")
            self.r.hide_spinner()
            self.r.system_message(str(result)[:200] if result else "Indexing complete.")
        except (ValueError, RuntimeError, OSError) as e:
            self.r.hide_spinner()
            self.r.error(f"Index: {e}")


    def _cmd_browser(self, args: str):
        if not args:
            self.r.system_message("Usage: /browser <url> [--js]")
            return
        
        use_js = False
        url = args
        if "--js" in args:
            use_js = True
            url = args.replace("--js", "").strip()
        
        if not url:
            self.r.system_message("Usage: /browser <url> [--js]")
            return

        if use_js:
            try:
                import playwright
            except ImportError:
                self.r.error("Browser automation requires Playwright. Run 'pip install playwright && playwright install' to enable.")
                return
        
        self.r.show_spinner("Opening browser")
        try:
            from nexus_agent.tools.browser import BrowserTool
            tool = BrowserTool()
            result = tool.execute(action="navigate", url=url, use_js=use_js)
            self.r.hide_spinner()
            
            content = result if isinstance(result, str) else str(result)
            
            if use_js and "Fallback Mode" in content:
                self.r.system_message("Note: JS is disabled in fallback mode. Please install playwright for JS support.")

            if len(content) > 3000:
                content = content[:3000] + f"\n  ... (truncated, {len(content)} total chars)"
            self.r.assistant_message(content)
        except (ValueError, RuntimeError, OSError, FileNotFoundError) as e:
            self.r.hide_spinner()
            self.r.error(f"Browser: {e}")


    def _cmd_mcp(self, args: str):
        if args == "list" or not args:
            if self._mcp_clients:
                for i, client in enumerate(self._mcp_clients):
                    tools = getattr(client, "discovered_tools", [])
                    self.console.print(f"  [cyan]MCP Server {i + 1}:[/cyan] {' '.join(client.command[:2])}")
                    self.console.print(f"    Tools: {len(tools)} registered")
                    for t in tools[:5]:
                        self.console.print(f"    - [bold]{t.name}[/bold]: {t.description[:60]}")
            else:
                self.r.system_message("No MCP servers connected.")
                self.console.print("  [dim]Configure servers in config mcp.servers[/dim]")
        elif args.startswith("connect "):
            cmd_parts = args[7:].strip().split()
            if cmd_parts:
                try:
                    from nexus_agent.mcp.client import MCPClient
                    client = MCPClient(command=cmd_parts)
                    if client.start():
                        self._mcp_clients.append(client)
                        self._mcp_tools.extend(client.discovered_tools)
                        if self._agent:
                            for tool in client.discovered_tools:
                                self._agent._tool_map[tool.name] = tool
                        self.r.system_message(f"MCP server connected ({len(client.discovered_tools)} tools)")
                    else:
                        self.r.error("MCP server failed to start")
                except (ValueError, RuntimeError, OSError, FileNotFoundError) as e:
                    self.r.error(f"MCP connect: {e}")
        elif args.startswith("install "):
            cmd_parts = args[8:].strip().split()
            if cmd_parts:
                try:
                    from nexus_agent.mcp.client import MCPClient
                    client = MCPClient(command=cmd_parts)
                    if client.start():
                        self._mcp_clients.append(client)
                        self._mcp_tools.extend(client.discovered_tools)
                        if self._agent:
                            for tool in client.discovered_tools:
                                self._agent._tool_map[tool.name] = tool

                        cmd_prefix = cmd_parts[0]
                        cmd_args = cmd_parts[1:]
                        servers = self._config.setdefault("mcp", {}).setdefault("servers", [])
                        if not any(s.get("command") == cmd_prefix and s.get("args") == cmd_args for s in servers):
                            servers.append({"command": cmd_prefix, "args": cmd_args})
                            save_config(self._config, self.config_path)
                            self.r.system_message("MCP server registered in config.yaml permanently")

                        self.r.system_message(f"MCP server installed & tools loaded dynamically ({len(client.discovered_tools)} tools)")
                    else:
                        self.r.error("MCP server failed to start")
                except (ValueError, RuntimeError, OSError, FileNotFoundError, TypeError) as e:
                    self.r.error(f"MCP install: {e}")


    def _cmd_skill(self, args: str):
        if not self._skill_registry:
            self.r.system_message("Skill registry unavailable.")
            return
        skills = self._skill_registry.skills
        if args == "list" or not args:
            if skills:
                for name, skill in skills.items():
                    self.console.print(f"  [bold]{name}[/bold]: {skill.description[:70]}")
            else:
                self.r.system_message("No skills discovered.")
                self.console.print("  [dim]Place .md skill files in ~/.nexus-agent/skills/[/dim]")
        elif args.startswith("run "):
            skill_name = args[4:].strip()
            if skill_name in skills:
                self.r.show_spinner(f"Running skill: {skill_name}")
                try:
                    result = skills[skill_name].execute()
                    self.r.hide_spinner()
                    self.r.assistant_message(str(result)[:2000])
                except (ValueError, RuntimeError, OSError) as e:
                    self.r.hide_spinner()
                    self.r.error(f"Skill: {e}")
            else:
                self.r.error(f"Skill not found: {skill_name}")
