"""NexusAgent CLI entry point."""

import os
import sys
from pathlib import Path

import click

from nexus_agent import __app_name__, __version__
from typing import Any


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name=__app_name__)
@click.option("--model", "-m", type=str, default=None, help="Path to GGUF model file or model name")
@click.option("--model-path", type=click.Path(exists=True), default=None, help="Path to model file on disk")
@click.option("--provider", "-p", type=str, default=None, help="LLM provider: local, openai, anthropic, etc.")
@click.option("--offline", is_flag=True, default=False, help="Force offline mode (local model only)")
@click.option("--gpu-layers", type=int, default=None, help="Number of layers to offload to GPU (requires CUDA)")
@click.option("--config", "-c", type=click.Path(exists=True), default=None, help="Path to config file")
@click.option("--data-dir", type=click.Path(), default=None, help="Data directory for sessions/memory")
@click.option("--verbose", is_flag=True, default=False, help="Show verbose debug output")
@click.option("--quiet", is_flag=True, default=False, help="Suppress non-essential output")
@click.pass_context
def cli(ctx: click.Context, model: str | None, model_path: str | None, provider: str | None,
        offline: bool, gpu_layers: int | None, config: str | None, data_dir: str | None,
        verbose: bool, quiet: bool) -> None:
    """NexusAgent — Offline-First LLM Coding Agent.

    Run local LLM models for AI-powered coding assistance with a rich
    terminal interface or web-based GUI.

    If no subcommand is given, launches the interactive TUI.
    """
    ctx.ensure_object(dict)
    model_val = model or model_path or os.environ.get("NEXUS_MODEL_PATH")
    ctx.obj["model"] = model_val
    ctx.obj["provider"] = provider or ("local" if offline else None)
    ctx.obj["offline"] = offline
    ctx.obj["gpu_layers"] = gpu_layers
    ctx.obj["config_path"] = config
    ctx.obj["data_dir"] = data_dir
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet

    if ctx.invoked_subcommand is None:
        ctx.invoke(chat)


@cli.command()
def wizard() -> None:
    """Run the interactive first-run setup wizard."""
    from rich.console import Console

    from nexus_agent.cli.wizard import SetupWizard

    console = Console()
    console.print("[bold magenta]Launching NexusAgent Setup Wizard...[/bold magenta]\n")
    wizard = SetupWizard(console=console)
    wizard.run()

@cli.command()
@click.option("--prompt", "-p", type=str, default=None, help="Initial prompt (non-interactive mode)")
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".", help="Working directory")
@click.option("--session", "-s", type=str, default=None, help="Session ID to resume")
@click.option("--new", "-n", is_flag=True, default=False, help="Start a new session instead of resuming the last active one")
@click.option("--verbose", is_flag=True, default=False, help="Show verbose output")
@click.option("--quiet", is_flag=True, default=False, help="Minimal output")
@click.pass_context
def chat(ctx: click.Context, prompt: str | None, workspace: str,
         session: str | None, new: bool, verbose: bool, quiet: bool) -> None:
    """Start an interactive chat session (TUI mode)."""
    from nexus_agent.cli.app import NexusApp

    workspace_path = Path(workspace).resolve()
    app = NexusApp(
        model_path=ctx.obj.get("model"),
        provider=ctx.obj.get("provider"),
        workspace=workspace_path,
        gpu_layers=ctx.obj.get("gpu_layers"),
        config_path=ctx.obj.get("config_path"),
        data_dir=ctx.obj.get("data_dir"),
        initial_prompt=prompt,
        session_id=session,
        new_session=new,
        verbose=verbose,
        quiet=quiet,
    )
    app.run()


@cli.command()
@click.option("--host", "-h", type=str, default=None, help="Host to bind to")
@click.option("--port", type=int, default=None, help="Port to bind to")
@click.option("--no-browser", is_flag=True, default=False, help="Don't open browser automatically")
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".", help="Working directory")
@click.pass_context
def gui(ctx: click.Context, host: str | None, port: int | None,
        no_browser: bool, workspace: str) -> None:
    """Launch the web-based GUI."""
    from nexus_agent.gui.server import start_gui_server

    workspace_path = Path(workspace).resolve()
    start_gui_server(
        model_path=ctx.obj.get("model"),
        provider=ctx.obj.get("provider"),
        workspace=workspace_path,
        config_path=ctx.obj.get("config_path"),
        data_dir=ctx.obj.get("data_dir"),
        host=host,
        port=port,
        open_browser=not no_browser,
    )


@cli.group()
def model() -> None:
    """Manage local LLM models."""
    pass


@model.command("list")
@click.option("--dir", "-d", "models_dir", type=click.Path(exists=True), default=None,
              help="Directory to scan for models")
def model_list(models_dir: str | None) -> None:
    """List available GGUF models."""
    from rich.console import Console
    from rich.table import Table

    from nexus_agent.llm.model_manager import ModelManager

    console = Console()
    manager = ModelManager(models_dir=models_dir)
    models = manager.discover_models()

    if not models:
        console.print("[yellow]No GGUF models found.[/yellow]")
        console.print(f"Place .gguf files in: {manager.models_dir}")
        return

    table = Table(title="Available Models", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Size", justify="right", style="green")
    table.add_column("Quantization", style="yellow")
    table.add_column("Path", style="dim")

    for m in models:
        table.add_row(m["name"], m["size_str"], m.get("quantization", "unknown"), str(m["path"]))

    console.print(table)


@model.command("info")
@click.argument("model_path", type=click.Path(exists=True))
def model_info(model_path: str) -> None:
    """Show detailed info about a GGUF model."""
    from rich.console import Console
    from rich.panel import Panel

    from nexus_agent.llm.model_manager import ModelManager

    console = Console()
    manager = ModelManager()
    info = manager.get_model_info(model_path)

    if info:
        console.print(Panel.fit(
            "\n".join(f"[cyan]{k}:[/cyan] {v}" for k, v in info.items()),
            title=f"Model: {Path(model_path).name}",
            border_style="magenta",
        ))
    else:
        console.print(f"[red]Could not read model info from {model_path}[/red]")


@cli.group()
def session() -> None:
    """Manage agent sessions."""
    pass


@session.command("list")
def session_list() -> None:
    """List saved sessions."""
    from rich.console import Console
    from rich.table import Table

    from nexus_agent.session.manager import SessionManager

    console = Console()
    mgr = SessionManager()
    sessions = mgr.list_sessions()

    if not sessions:
        console.print("[yellow]No saved sessions found.[/yellow]")
        return

    table = Table(title="Sessions", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    table.add_column("Created", style="green")
    table.add_column("Messages", justify="right", style="yellow")
    table.add_column("Model", style="dim")

    for s in sessions:
        table.add_row(s["id"][:12], s["created"], str(s["message_count"]), s.get("model", ""))

    console.print(table)


@session.command("resume")
@click.argument("session_id", type=str)
def session_resume(session_id: str) -> None:
    """Resume a saved session."""
    from nexus_agent.cli.app import NexusApp

    app = NexusApp(session_id=session_id)
    app.run()


@session.command("checkpoint")
@click.argument("description", type=str, default="Manual checkpoint")
def session_checkpoint(description: str) -> None:
    """Create a session checkpoint (snapshot of working tree)."""
    from rich.console import Console

    from nexus_agent.session.manager import SessionManager

    console = Console()
    mgr = SessionManager()
    from pathlib import Path
    files = [str(f) for f in Path.cwd().rglob("*.py")][:20]
    cp_id = mgr.create_checkpoint(files, description=description)
    console.print(f"[green]Checkpoint created:[/green] {cp_id[:12]}…")


@session.command("rollback")
@click.argument("checkpoint_id", type=str, required=False)
def session_rollback(checkpoint_id: str | None) -> None:
    """Rollback to a previous checkpoint."""
    from rich.console import Console

    from nexus_agent.session.manager import SessionManager

    console = Console()
    mgr = SessionManager()
    try:
        results = mgr.rollback(checkpoint_id)
        for k, v in results.items():
            console.print(f"  {k}: {v}")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")


@cli.group()
def config() -> None:
    """Manage configuration."""
    pass


@config.command("show")
def config_show() -> None:
    """Show current configuration."""
    import json

    from rich.console import Console

    from nexus_agent.core.config import load_config

    console = Console()
    cfg = load_config()
    console.print_json(json.dumps(cfg, indent=2, default=str))


@config.command("set")
@click.argument("key", type=str)
@click.argument("value", type=str)
def config_set(key: str, value: str) -> None:
    """Set a config value persistently (saves to ~/.nexus-agent/config.yaml).

    Example: nexus config set model_path C:\\models\\my-model.gguf
    """
    from rich.console import Console

    from nexus_agent.core.config import save_user_config

    console = Console()
    # Support dot-notation: model.path -> {"model": {"path": value}}
    keys = key.split(".")
    updates = {}
    target = updates
    for k in keys[:-1]:
        target[k] = {}
        target = target[k]
    target[keys[-1]] = value

    save_user_config(updates)
    console.print(f"[green]Saved[/green] {key} = {value}")


@config.command("get")
@click.argument("key", type=str, required=False)
def config_get(key: str | None) -> None:
    """Get a config value.

    Example: nexus config get model_path
    """
    from rich.console import Console

    from nexus_agent.core.config import load_config

    console = Console()
    cfg = load_config()
    if key:
        keys = key.split(".")
        val = cfg
        try:
            for k in keys:
                val = val[k]
            console.print(f"{key} = {val}")
        except (KeyError, TypeError):
            console.print(f"[red]Key not found: {key}[/red]")
    else:
        import json
        console.print_json(json.dumps(cfg, indent=2, default=str))


@cli.command()
def hardware() -> None:
    """Show hardware capabilities for model hosting."""
    from rich.console import Console
    from rich.panel import Panel

    from nexus_agent.llm.model_manager import ModelManager

    console = Console()
    manager = ModelManager()
    hw = manager.detect_hardware()

    lines = [
        f"[cyan]CPU:[/cyan] {hw.get('cpu', 'unknown')}",
        f"[cyan]CPU Threads:[/cyan] {hw.get('cpu_threads', 'unknown')}",
        f"[cyan]Total RAM:[/cyan] {hw.get('ram_total', 'unknown')}",
        f"[cyan]Available RAM:[/cyan] {hw.get('ram_available', 'unknown')}",
        f"[cyan]GPU:[/cyan] {hw.get('gpu', 'Not detected')}",
        f"[cyan]VRAM:[/cyan] {hw.get('vram', 'N/A')}",
        "",
        f"[bold green]Recommended max model size:[/bold green] {hw.get('recommended_model_size', 'unknown')}",
    ]

    console.print(Panel.fit(
        "\n".join(lines),
        title="Hardware Capabilities",
        border_style="magenta",
    ))


@cli.command()
@click.argument("url", type=str)
@click.option("--action", type=click.Choice(["navigate", "read", "screenshot"]), default="navigate",
              help="Browser action to perform")
@click.pass_context
def browse(ctx: click.Context, url: str, action: str) -> None:
    """Browse a URL and return content as markdown.

    Uses Playwright if available, falls back to HTTPX + HTML parser.
    """
    from rich.console import Console
    from rich.panel import Panel

    from nexus_agent.tools.browser import BrowserTool

    console = Console()
    tool = BrowserTool()
    try:
        result = tool.execute(action=action, url=url)
        if result:
            content = str(result)[:3000]
            console.print(Panel.fit(content[:500], title=f"Browser: {url}", border_style="cyan"))
        else:
            console.print("[yellow]No content returned.[/yellow]")
    except (OSError, ValueError, RuntimeError) as e:
        console.print(f"[red]Browse failed: {e}[/red]")


@cli.command()
@click.argument("task", type=str)
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".", help="Working directory")
@click.option("--model-path", type=click.Path(exists=True), help="Model to use")
@click.pass_context
def plan(ctx: click.Context, task: str, workspace: str, model_path: str | None) -> None:
    """Generate an implementation plan for a task (read-only analysis).

    Analyzes the repository and produces a detailed plan without making changes.
    """
    from rich.console import Console
    from rich.panel import Panel

    from nexus_agent.core.planner import Planner
    from nexus_agent.llm.providers.factory import ProviderFactory

    console = Console()
    ws = Path(workspace).resolve()
    cfg_path = ctx.obj.get("config_path")
    from nexus_agent.core.config import load_config
    config = load_config(config_path=cfg_path, workspace=ws)
    provider_name = ctx.obj.get("provider") or "local"
    engine = ProviderFactory.create_provider(provider_name, config, model_path)
    tools = []
    from nexus_agent.tools.file_ops import ListDirectoryTool, ReadFileTool, SearchFilesTool
    from nexus_agent.tools.shell import ShellTool
    tools.extend([ReadFileTool(ws), SearchFilesTool(ws), ListDirectoryTool(ws), ShellTool(ws)])

    planner = Planner(provider=engine, tools=tools, workspace=ws, max_iterations=15)
    console.print(f"[bold cyan]◆ Planning:[/bold cyan] {task[:80]}\n")
    full_plan = ""
    for event in planner.plan(task):
        if event.type == "content_chunk":
            full_plan += event.data
            sys.stdout.write(event.data)
            sys.stdout.flush()
        elif event.type == "error":
            console.print(f"\n[red]Error: {event.data}[/red]")
    console.print("\n")
    console.print(Panel.fit("[bold green]Plan Complete (read-only mode)[/bold green]", border_style="green"))


@cli.command()
@click.option("--model", "-m", type=str, default=None,
              help="Path to GGUF model for benchmarking")
@click.option("--provider", "-p", type=str, default="local",
              help="Provider to benchmark (local, openai, anthropic, etc.)")
@click.option("--benchmark/--no-benchmark", default=True,
              help="Run cold-start and first-token benchmarks")
@click.option("--json", "json_output", is_flag=True, default=False,
              help="Output as JSON")
def doctor(model: str | None, provider: str, benchmark: bool, json_output: bool) -> None:
    """Diagnose installation and benchmark cold-start + first-token latency.

    Checks system hardware, Python environment, key packages, and runs
    performance benchmarks for cold-start and first-token latency.

    Examples:

        nexus doctor

        nexus doctor --model path/to/model.gguf

        nexus doctor --model path/to/model.gguf --json
    """
    from rich.console import Console

    from nexus_agent.cli.doctor import run_doctor, print_report

    console = Console()

    if json_output:
        import json as _json
        report = run_doctor(model_path=model, provider=provider, run_benchmarks=benchmark)
        data: dict[str, Any] = {
            "timestamp": report.timestamp,
            "system": [
                {"name": m.name, "value": m.value, "unit": m.unit, "status": m.status}
                for m in report.system
            ],
            "python_env": [
                {"name": m.name, "value": m.value, "unit": m.unit, "status": m.status}
                for m in report.python_env
            ],
            "benchmarks": None,
        }
        if report.benchmarks:
            data["benchmarks"] = {
                "cold_start_ms": report.benchmarks.cold_start_ms,
                "first_token_ms": report.benchmarks.first_token_ms,
                "model_path": report.benchmarks.model_path,
                "provider": report.benchmarks.provider,
                "model_name": report.benchmarks.model_name,
                "error": report.benchmarks.error,
            }
        console.print(_json.dumps(data, indent=2))
        return

    report = run_doctor(model_path=model, provider=provider, run_benchmarks=benchmark)
    print_report(report)


@cli.command()
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".", help="Working directory")
def devops(workspace: str) -> None:
    """Run the DevOps verification pipeline (linters, secrets, tests)."""
    from rich.console import Console

    from nexus_agent.core.devops import VerificationPipeline

    console = Console()
    ws = Path(workspace).resolve()
    pipeline = VerificationPipeline(workspace=ws)
    console.print("[bold cyan]◆ Running DevOps Verification Pipeline...[/bold cyan]\n")
    report = pipeline.run_full_pipeline()
    console.print(f"[bold]Status:[/bold] {'✅ SUCCESS' if report.success else '❌ FAILURE'}")
    console.print(f"  Test framework: {report.test_framework_detected or 'None'}")
    console.print(f"  Tests passed: {report.tests_passed}")
    console.print(f"  Linters passed: {report.linters_passed}")
    if report.secrets_found:
        console.print("[bold yellow]  Secrets found:[/bold yellow]")
        for s in report.secrets_found:
            console.print(f"    - {s.file_path}:{s.line_number} ({s.pattern_name})")


@cli.command()
@click.option("--acp", is_flag=True, help="Run as ACP stdio backend (for Rust CLI)")
@click.option("--dry-run", is_flag=True, help="Test initialization and exit")
@click.option("--workspace", type=click.Path(exists=False), default=".", help="Working directory")
@click.option("--model", type=str, default=None, help="Model path or alias")
@click.option("--provider", type=str, default=None, help="Provider name")
@click.option("--verbose", is_flag=True, default=False, help="Enable verbose logging")
@click.pass_context
def backend(ctx: click.Context, acp: bool, dry_run: bool, workspace: str,
            model: str | None, provider: str | None, verbose: bool) -> None:
    """Run as backend process for the Rust CLI (ACP mode).

    Spawned automatically by the Rust `nexus chat` binary.
    """
    if not acp:
        click.echo("Usage: nexus backend --acp [options]")
        return
    from nexus_agent.backend import run_acp_backend, parse_args
    args = parse_args([
        "--acp",
        "--workspace", workspace,
        *(("--model", model) if model else []),
        *(("--provider", provider) if provider else []),
        *(["--verbose"] if verbose else []),
        *(["--dry-run"] if dry_run else []),
    ])
    run_acp_backend(args)


def main() -> None:
    """Main entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
