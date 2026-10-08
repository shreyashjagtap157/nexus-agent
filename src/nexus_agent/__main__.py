"""NexusAgent CLI entry point."""

import itertools
import os
import sys
from pathlib import Path
from typing import Any

import click

from nexus_agent import __app_name__, __version__
from nexus_agent.utils.fs import iter_files


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name=__app_name__)
@click.option("--model", "-m", type=str, default=None, help="Path to GGUF model file or model name")
@click.option(
    "--model-path", type=click.Path(exists=True), default=None, help="Path to model file on disk"
)
@click.option(
    "--provider", "-p", type=str, default=None, help="LLM provider: local, openai, anthropic, etc."
)
@click.option(
    "--offline", is_flag=True, default=False, help="Force offline mode (local model only)"
)
@click.option(
    "--gpu-layers",
    type=int,
    default=None,
    help="Number of layers to offload to GPU (requires CUDA)",
)
@click.option(
    "--config", "-c", type=click.Path(exists=True), default=None, help="Path to config file"
)
@click.option(
    "--data-dir", type=click.Path(), default=None, help="Data directory for sessions/memory"
)
@click.option("--verbose", is_flag=True, default=False, help="Show verbose debug output")
@click.option("--quiet", is_flag=True, default=False, help="Suppress non-essential output")
@click.pass_context
def cli(
    ctx: click.Context,
    model: str | None,
    model_path: str | None,
    provider: str | None,
    offline: bool,
    gpu_layers: int | None,
    config: str | None,
    data_dir: str | None,
    verbose: bool,
    quiet: bool,
) -> None:
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
@click.option(
    "--prompt", "-p", type=str, default=None, help="Initial prompt (non-interactive mode)"
)
@click.option(
    "--workspace", "-w", type=click.Path(exists=True), default=".", help="Working directory"
)
@click.option("--session", "-s", type=str, default=None, help="Session ID to resume")
@click.option(
    "--new",
    "-n",
    is_flag=True,
    default=False,
    help="Start a new session instead of resuming the last active one",
)
@click.option("--verbose", is_flag=True, default=False, help="Show verbose output")
@click.option("--quiet", is_flag=True, default=False, help="Minimal output")
@click.pass_context
def chat(
    ctx: click.Context,
    prompt: str | None,
    workspace: str,
    session: str | None,
    new: bool,
    verbose: bool,
    quiet: bool,
) -> None:
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


@cli.command("serve")
@click.option("--host", "-h", type=str, default=None, help="Host to bind the local agent API")
@click.option("--port", type=int, default=None, help="Port for the local agent API")
@click.option("--workspace", "-w", type=click.Path(exists=True), default=".", help="Working directory")
@click.option("--provider", "-p", type=str, default=None, help="LLM provider")
@click.option("--model-path", type=click.Path(exists=True), default=None, help="Local model path")
@click.pass_context
def serve(ctx: click.Context, host: str | None, port: int | None, workspace: str, provider: str | None, model_path: str | None) -> None:
    """Run the NexusAgent local API/web server without opening a browser."""
    from nexus_agent.gui.server import start_gui_server
    start_gui_server(
        model_path=model_path or ctx.obj.get("model"),
        provider=provider or ctx.obj.get("provider"),
        workspace=Path(workspace).resolve(),
        config_path=ctx.obj.get("config_path"),
        data_dir=ctx.obj.get("data_dir"),
        host=host,
        port=port,
        open_browser=False,
    )


@cli.command()
@click.option("--host", "-h", type=str, default=None, help="Host to bind to")
@click.option("--port", type=int, default=None, help="Port to bind to")
@click.option("--no-browser", is_flag=True, default=False, help="Don't open browser automatically")
@click.option(
    "--workspace", "-w", type=click.Path(exists=True), default=".", help="Working directory"
)
@click.pass_context
def gui(
    ctx: click.Context, host: str | None, port: int | None, no_browser: bool, workspace: str
) -> None:
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
@click.option(
    "--dir",
    "-d",
    "models_dir",
    type=click.Path(exists=True),
    default=None,
    help="Directory to scan for models",
)
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
        console.print(
            Panel.fit(
                "\n".join(f"[cyan]{k}:[/cyan] {v}" for k, v in info.items()),
                title=f"Model: {Path(model_path).name}",
                border_style="magenta",
            )
        )
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

    files = [
        str(f)
        for f in itertools.islice((f for f in iter_files(Path.cwd()) if f.suffix == ".py"), 20)
    ]
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

    console.print(
        Panel.fit(
            "\n".join(lines),
            title="Hardware Capabilities",
            border_style="magenta",
        )
    )


@cli.command()
@click.argument("url", type=str)
@click.option(
    "--action",
    type=click.Choice(["navigate", "read", "screenshot"]),
    default="navigate",
    help="Browser action to perform",
)
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
@click.option(
    "--workspace", "-w", type=click.Path(exists=True), default=".", help="Working directory"
)
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
    console.print(
        Panel.fit("[bold green]Plan Complete (read-only mode)[/bold green]", border_style="green")
    )


@cli.command()
@click.option("--model", "-m", type=str, default=None, help="Path to GGUF model for benchmarking")
@click.option(
    "--provider",
    "-p",
    type=str,
    default="local",
    help="Provider to benchmark (local, openai, anthropic, etc.)",
)
@click.option(
    "--benchmark/--no-benchmark", default=True, help="Run cold-start and first-token benchmarks"
)
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON")
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

    from nexus_agent.cli.doctor import print_report, run_doctor

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
@click.option(
    "--workspace", "-w", type=click.Path(exists=True), default=".", help="Working directory"
)
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
def backend(
    ctx: click.Context,
    acp: bool,
    dry_run: bool,
    workspace: str,
    model: str | None,
    provider: str | None,
    verbose: bool,
) -> None:
    """Run as backend process for the Rust CLI (ACP mode).

    Spawned automatically by the Rust `nexus chat` binary.
    """
    if not acp:
        click.echo("Usage: nexus backend --acp [options]")
        return
    from nexus_agent.backend import parse_args, run_acp_backend

    args = parse_args(
        [
            "--acp",
            "--workspace",
            workspace,
            *(("--model", model) if model else []),
            *(("--provider", provider) if provider else []),
            *(["--verbose"] if verbose else []),
            *(["--dry-run"] if dry_run else []),
        ]
    )
    run_acp_backend(args)



@cli.group()
def agent() -> None:
    """Create, configure, validate and generate reusable agent profiles."""
    pass


@agent.command("list")
@click.option(
    "--workspace", "-w", type=click.Path(exists=True, file_okay=False), default="."
)
def agent_list(workspace: str) -> None:
    """List resolved agent profiles after scope precedence is applied."""
    from rich.console import Console
    from rich.table import Table
    from nexus_agent.agents import AgentRegistry

    console = Console()
    registry = AgentRegistry(Path(workspace).resolve())
    rows = registry.load(include_disabled=True)
    table = Table(title="NexusAgent Agents")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Profession")
    table.add_column("Scope")
    table.add_column("Tools")
    table.add_column("Write")
    table.add_column("State")
    for item in rows:
        table.add_row(
            item.id,
            item.name,
            item.profession,
            item.scope.value,
            ",".join(item.tool_categories),
            "yes" if item.write_access else "no",
            "enabled" if item.enabled else "disabled",
        )
    console.print(table)


@agent.command("show")
@click.argument("agent_id")
@click.option("--workspace", "-w", type=click.Path(exists=True, file_okay=False), default=".")
def agent_show(agent_id: str, workspace: str) -> None:
    """Show one resolved agent profile."""
    import json
    from nexus_agent.agents import AgentRegistry

    spec = AgentRegistry(Path(workspace).resolve()).get(agent_id)
    if spec is None:
        raise click.ClickException(f"Unknown or disabled agent: {agent_id}")
    click.echo(json.dumps(spec.to_dict(), indent=2, ensure_ascii=False, default=str))


@agent.command("paths")
@click.option("--workspace", "-w", type=click.Path(exists=True, file_okay=False), default=".")
def agent_paths(workspace: str) -> None:
    """Show agent definition storage paths for every scope."""
    import json
    from nexus_agent.agents import AgentRegistry

    click.echo(json.dumps(
        AgentRegistry(Path(workspace).resolve()).roots_info(),
        indent=2,
        ensure_ascii=False,
    ))


@agent.command("init")
@click.argument("agent_id")
@click.option(
    "--scope",
    type=click.Choice(["user", "project", "workspace", "global"]),
    default="user",
    show_default=True,
)
@click.option("--workspace", "-w", type=click.Path(exists=True, file_okay=False), default=".")
def agent_init(agent_id: str, scope: str, workspace: str) -> None:
    """Create an editable agent profile template."""
    from nexus_agent.agents import AgentRegistry, AgentScope, AgentSpec

    aid = agent_id.strip().lower()
    spec = AgentSpec(
        id=aid,
        name=aid.replace("-", " ").replace("_", " ").title(),
        profession="Professional Specialist",
        description="Describe what this agent is uniquely responsible for.",
        mission="Define the result this agent owns.",
        instructions="Describe the exact operating procedure, constraints, evidence requirements and completion criteria.",
        tool_categories=["read", "search"],
    )
    registry = AgentRegistry(Path(workspace).resolve())
    errors = registry.validate(spec)
    if errors:
        raise click.ClickException("; ".join(errors))
    path = registry.save(spec, AgentScope(scope))
    click.echo(f"Created agent profile: {path}")


@agent.command("generate")
@click.argument("request")
@click.option("--max-agents", type=int, default=6, show_default=True)
@click.option(
    "--scope",
    type=click.Choice(["user", "project", "workspace", "global"]),
    default="user",
    show_default=True,
)
@click.option("--workspace", "-w", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--provider", type=str, default=None)
@click.option("--model-path", type=click.Path(exists=True), default=None)
@click.option("--preview", is_flag=True, help="Generate and print profiles without saving them.")
@click.pass_context
def agent_generate(
    ctx: click.Context,
    request: str,
    max_agents: int,
    scope: str,
    workspace: str,
    provider: str | None,
    model_path: str | None,
    preview: bool,
) -> None:
    """Ask NexusAgent to design reusable professional agents for a requirement."""
    import json
    from nexus_agent.agents import AgentGenerator, AgentRegistry, AgentScope
    from nexus_agent.core.config import load_config
    from nexus_agent.llm.providers.factory import ProviderFactory

    ws = Path(workspace).resolve()
    config = load_config(config_path=ctx.obj.get("config_path"), workspace=ws)
    provider_name = provider or config.get("providers", {}).get("active", "local")
    llm = ProviderFactory.create_provider(provider_name, config, model_path)
    specs = AgentGenerator(llm).generate(request, max_agents=max(1, min(max_agents, 32)))
    registry = AgentRegistry(ws)
    if preview:
        click.echo(json.dumps([spec.to_dict() for spec in specs], indent=2, ensure_ascii=False, default=str))
        return
    target_scope = AgentScope(scope)
    for spec in specs:
        errors = registry.validate(spec)
        if errors:
            raise click.ClickException(f"{spec.id}: {'; '.join(errors)}")
        path = registry.save(spec, target_scope)
        click.echo(f"Saved {spec.id}: {path}")


@agent.command("validate")
@click.option("--workspace", "-w", type=click.Path(exists=True, file_okay=False), default=".")
def agent_validate(workspace: str) -> None:
    """Validate every resolved agent definition."""
    from nexus_agent.agents import AgentRegistry

    registry = AgentRegistry(Path(workspace).resolve())
    failures = 0
    for spec in registry.load(include_disabled=True):
        errors = registry.validate(spec)
        if errors:
            failures += 1
            click.echo(f"{spec.id}: " + "; ".join(errors))
    if failures:
        raise click.ClickException(f"{failures} agent profile(s) failed validation.")
    click.echo("All agent profiles are valid.")


@agent.command("delete")
@click.argument("agent_id")
@click.option(
    "--scope",
    type=click.Choice(["user", "project", "workspace", "global"]),
    default=None,
)
@click.option("--workspace", "-w", type=click.Path(exists=True, file_okay=False), default=".")
def agent_delete(agent_id: str, scope: str | None, workspace: str) -> None:
    """Remove a persisted agent definition from one or all mutable scopes."""
    from nexus_agent.agents import AgentRegistry, AgentScope

    registry = AgentRegistry(Path(workspace).resolve())
    removed = registry.delete(agent_id, AgentScope(scope) if scope else None)
    if not removed:
        raise click.ClickException(f"No persisted definition found for {agent_id}")
    for path in removed:
        click.echo(f"Deleted: {path}")


@cli.group()
def team() -> None:
    """Run and inspect dynamically assembled multi-agent teams."""
    pass


@team.command("run")
@click.argument("goal", type=str)
@click.option("--mode", type=click.Choice(["auto", "code", "research", "review", "analysis", "plan", "automation"]), default="auto")
@click.option("--max-agents", type=int, default=6, show_default=True)
@click.option("--parallelism", type=int, default=4, show_default=True)
@click.option("--max-iterations", type=int, default=30, show_default=True)
@click.option("--effort", type=click.Choice(["low", "medium", "high", "xhigh", "max"]), default="medium")
@click.option("--output", "output_mode", type=click.Choice(["chat", "file", "both"]), default="chat")
@click.option("--format", "output_format", type=click.Choice(["markdown", "text", "json"]), default="markdown")
@click.option("--depth", "research_depth", type=click.Choice(list(RESEARCH_DEPTHS)), default="detailed", show_default=True)
@click.option("--collection", "research_collection", type=click.Choice(["bounded", "until_saturation", "continuous"]), default="until_saturation", show_default=True)
@click.option("--workspace", "-w", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--provider", type=str, default=None)
@click.option("--model-path", type=click.Path(exists=True), default=None)
@click.option("--yes", is_flag=True, help="Automatically approve team tool requests.")
def team_run(goal: str, mode: str, max_agents: int, parallelism: int, max_iterations: int, effort: str, output_mode: str, output_format: str, research_depth: str, research_collection: str, workspace: str, provider: str | None, model_path: str | None, yes: bool) -> None:
    """Execute a dynamically assembled peer team."""
    from rich.console import Console
    from rich.table import Table
    from nexus_agent.permissions.manager import PermissionManager
    from nexus_agent.core.config import load_config
    from nexus_agent.team import TeamConfig, TeamMode, TeamRuntime, build_workspace_tools
    from nexus_agent.team.providers import make_provider_selector
    from nexus_agent.team.research import RESEARCH_DEPTHS
    from nexus_agent.llm.providers.factory import ProviderFactory

    console = Console()
    ws = Path(workspace).resolve()
    config = load_config(workspace=ws)
    provider_name = provider or config.get("providers", {}).get("active", "local")
    llm = ProviderFactory.create_provider(provider_name, config, model_path)
    permissions = PermissionManager(project=str(ws))
    permissions.load_from_config(config)
    runtime = TeamRuntime(
        llm,
        build_workspace_tools(ws),
        workspace=ws,
        permission_callback=lambda tc: permissions.check_and_approve(
            tool_name=tc.name,
            arguments=tc.arguments,
            description=f"Team worker requesting {tc.name}",
        ),
        provider_selector=make_provider_selector(config, llm),
    )
    team_config = TeamConfig(
        mode=TeamMode(mode),
        max_agents=max_agents,
        parallelism=parallelism,
        max_iterations_per_agent=max_iterations,
        workspace=str(ws),
        effort_level=effort,
        output_mode=output_mode,
        output_format=output_format,
        research_depth=research_depth,
        research_collection=research_collection,
        auto_approve_tools=yes,
    )
    final = None
    for event in runtime.run(goal, team_config):
        if event.type.value == "state_change":
            console.print(f"[cyan]TEAM[/cyan] {event.data}")
        elif event.type.value == "content":
            if isinstance(event.data, dict) and event.data.get("agent_id"):
                console.print(f"[green]{event.data.get('agent_id')}[/green] {event.data.get('status', 'event')}")
            else:
                console.print(str(event.data))
        elif event.type.value == "done" and isinstance(event.data, dict):
            final = event.data
    if final is None:
        raise click.ClickException("Team runtime ended without a result.")
    console.print(f"[bold green]{final.get('summary', '')}[/bold green]")
    if final.get("synthesis"):
        console.print(final["synthesis"])
    table = Table(title="Team Workers")
    table.add_column("Agent")
    table.add_column("Profession")
    table.add_column("State")
    for agent in final.get("agents", []):
        table.add_row(str(agent.get("name")), str(agent.get("profession")), str(agent.get("status")))
    console.print(table)


@team.command("show")
@click.argument("team_id", type=str)
@click.option("--workspace", "-w", type=click.Path(exists=True, file_okay=False), default=".")
def team_show(team_id: str, workspace: str) -> None:
    """Inspect a persisted team run as JSON."""
    import json
    from nexus_agent.team import TeamStore
    store = TeamStore(Path(workspace).resolve() / ".nexus" / "teams.db")
    try:
        team_data = store.team(team_id)
        if team_data is None:
            raise click.ClickException(f"Unknown team: {team_id}")
        click.echo(json.dumps({
            "team": team_data,
            "agents": store.agents(team_id),
            "messages": store.messages(team_id),
            "events": store.events(team_id, limit=5000),
        }, indent=2, ensure_ascii=False, default=str))
    finally:
        store.close()


def main() -> None:
    """Main entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
