from pathlib import Path

f1 = Path("src/nexus_agent/__main__.py")
t1 = f1.read_text()
t1 = t1.replace(
    "f\"[bold green]Recommended max model size:[/bold green] {hw.get('recommended_model_size', 'unknown')}\",",
    "f\"[bold green]Recommended max model size:[/bold green] \"\n        f\"{hw.get('recommended_model_size', 'unknown')}\","
)
f1.write_text(t1)

f2 = Path("src/nexus_agent/cli/commands/session_mixin.py")
t2 = f2.read_text()
t2 = t2.replace(
    "f\"  [{cp['id'][:12]}] {cp.get('description', '')}  [dim]{cp.get('created', '')}[/dim]\"",
    "f\"  [{cp['id'][:12]}] {cp.get('description', '')}  \"\n                        f\"[dim]{cp.get('created', '')}[/dim]\""
)
f2.write_text(t2)
