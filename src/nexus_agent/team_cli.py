"""NexusAgent team CLI."""
from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from nexus_agent.core.config import load_config
from nexus_agent.mcp.client import load_configured_servers
from nexus_agent.llm.providers.factory import ProviderFactory
from nexus_agent.permissions.manager import PermissionManager
from nexus_agent.storage.layout import StorageLayout

from .team.models import TeamConfig, TeamMode
from .team.runtime import TeamRuntime, build_workspace_tools
from .team.providers import make_provider_selector
from .team.research import RESEARCH_DEPTHS
from .team.store import TeamStore


def _make_runtime(workspace: Path, provider_name: str | None, model_path: str | None, auto_approve: bool):
    config = load_config(workspace=workspace)
    name = provider_name or config.get("providers", {}).get("active", "local")
    provider = ProviderFactory.create_provider(name, config, model_path)
    permissions = PermissionManager(project=str(workspace))
    permissions.load_from_config(config)
    mcp_clients, mcp_tools = load_configured_servers(config)
    tools = build_workspace_tools(workspace, mcp_tools=mcp_tools)
    runtime = TeamRuntime(
        provider,
        tools,
        workspace=workspace,
        permission_callback=lambda tc: permissions.check_and_approve(
            tool_name=tc.name,
            arguments=tc.arguments,
            description=f"Team worker requesting {tc.name}",
        ),
        provider_selector=make_provider_selector(config, provider),
    )
    return runtime, provider


@click.group()
def main() -> None:
    """NexusAgent multi-agent team runner."""


@main.command("run")
@click.argument("goal")
@click.option("--mode", type=click.Choice([x.value for x in TeamMode]), default="auto", show_default=True)
@click.option("--max-agents", type=int, default=6, show_default=True)
@click.option("--parallelism", type=int, default=4, show_default=True)
@click.option("--max-iterations", type=int, default=30, show_default=True)
@click.option("--effort", type=click.Choice(["low", "medium", "high", "xhigh", "max"]), default="medium")
@click.option("--output", "output_mode", type=click.Choice(["chat", "file", "both"]), default="chat")
@click.option("--format", "output_format", type=click.Choice(["markdown", "text", "json"]), default="markdown")
@click.option("--depth", "research_depth", type=click.Choice(list(RESEARCH_DEPTHS)), default="detailed", show_default=True)
@click.option("--collection", "research_collection", type=click.Choice(["bounded", "until_saturation", "continuous"]), default="until_saturation", show_default=True)
@click.option("--workspace", "-w", type=click.Path(exists=True, file_okay=False, path_type=Path), default=Path.cwd())
@click.option("--provider", type=str, default=None)
@click.option("--model-path", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--yes", is_flag=True, help="Automatically approve team tool requests.")
def run(goal: str, mode: str, max_agents: int, parallelism: int, max_iterations: int, effort: str, output_mode: str, output_format: str, research_depth: str, research_collection: str, workspace: Path, provider: str | None, model_path: str | None, yes: bool) -> None:
    """Run a dynamically assembled peer team."""
    console = Console()
    runtime, _provider = _make_runtime(workspace.resolve(), provider, model_path, yes)
    config = TeamConfig(
        mode=TeamMode(mode),
        max_agents=max_agents,
        parallelism=parallelism,
        max_iterations_per_agent=max_iterations,
        workspace=str(workspace.resolve()),
        effort_level=effort,
        output_mode=output_mode,
        output_format=output_format,
        research_depth=research_depth,
        research_collection=research_collection,
        auto_approve_tools=yes,
    )
    final = None
    with Live(Panel.fit("Starting team…"), console=console, refresh_per_second=10):
        for event in runtime.run(goal, config):
            if event.type.value == "state_change":
                console.print(f"[cyan]TEAM[/cyan] {event.data}")
            elif event.type.value == "content":
                data = event.data
                if isinstance(data, dict) and data.get("agent_id"):
                    console.print(
                        f"[green]{data['agent_id']}[/green] "
                        f"{data.get('status', data.get('data', 'event'))}"
                    )
                else:
                    console.print(str(data))
            elif event.type.value == "done" and isinstance(event.data, dict):
                final = event.data

    if final is None:
        raise click.ClickException("Team runtime ended without a result.")

    console.print(Panel(final.get("synthesis") or final.get("summary", ""), title="Team Result"))
    if final.get("artifact_paths"):
        console.print("Artifacts:\n" + "\n".join(str(p) for p in final["artifact_paths"]))
    table = Table(title="Team")
    table.add_column("Agent")
    table.add_column("Profession")
    table.add_column("State")
    for agent in final.get("agents", []):
        table.add_row(str(agent.get("name")), str(agent.get("profession")), str(agent.get("status")))
    console.print(table)


@main.command("list")
@click.option("--workspace", "-w", type=click.Path(exists=True, file_okay=False, path_type=Path), default=Path.cwd())
@click.option("--limit", type=int, default=50, show_default=True)
def list_teams(workspace: Path, limit: int) -> None:
    """List persisted multi-agent team runs."""
    store = TeamStore(StorageLayout(workspace.resolve()).team_db)
    try:
        rows = store.list_teams(limit=max(1, min(limit, 1000)))
        if not rows:
            console.print("[yellow]No team runs found.[/yellow]")
            return
        table = Table(title="NexusAgent Teams")
        table.add_column("Team ID")
        table.add_column("Mode")
        table.add_column("Status")
        table.add_column("Created")
        table.add_column("Goal")
        for row in rows:
            table.add_row(
                str(row["team_id"]),
                str(row["mode"]),
                str(row["status"]),
                str(row["created_at"]),
                str(row["goal"])[:100],
            )
        console.print(table)
    finally:
        store.close()


@main.command("control")
@click.argument("team_id")
@click.argument("action", type=click.Choice(["pause", "resume", "stop"]))
@click.option("--workspace", "-w", type=click.Path(exists=True, file_okay=False, path_type=Path), default=Path.cwd())
def control_team(team_id: str, action: str, workspace: Path) -> None:
    """Request pause, resume or stop for a running team."""
    store = TeamStore(workspace.resolve() / ".nexus" / "teams.db")
    try:
        if not store.request_control(team_id, action):
            raise click.ClickException("Unknown or terminal team.")
        console.print(f"[green]Control request persisted:[/green] {action} -> {team_id}")
    finally:
        store.close()


@main.command("show")
@click.argument("team_id")
@click.option("--workspace", "-w", type=click.Path(exists=True, file_okay=False, path_type=Path), default=Path.cwd())
def show(team_id: str, workspace: Path) -> None:
    """Inspect a persisted team run."""
    store = TeamStore(workspace.resolve() / ".nexus" / "teams.db")
    try:
        team = store.team(team_id)
        if team is None:
            raise click.ClickException(f"Unknown team: {team_id}")
        console.print_json(json.dumps({
            "team": team,
            "agents": store.agents(team_id),
            "messages": store.messages(team_id),
            "events": store.events(team_id, limit=5000),
        }, ensure_ascii=False, indent=2, default=str))
    finally:
        store.close()


if __name__ == "__main__":
    main()
