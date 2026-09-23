#!/usr/bin/env python3
"""PasarGuard CLI"""

from pathlib import Path\n\nimport typer\n\nfrom app.migration.engine import plan_pasarguard_migration\n
from cli import console
from cli.admin import generate_temp_key

app = typer.Typer(
    name="PasarGuard",
    help="PasarGuard CLI",
    add_completion=False,
    rich_markup_mode="rich",
)


@app.command("migrate-check")
def cmd_migrate_check(backup: Path) -> None:
    """Inspect a legacy backup and print the non-destructive migration plan."""
    plan = plan_pasarguard_migration(backup)
    detection = plan.preflight.detection
    console.print(f"[bold]Source:[/bold] {detection.source_product} ({detection.confidence})")
    console.print(f"[bold]Format:[/bold] {detection.format}")
    if detection.evidence:
        console.print("[bold]Evidence:[/bold]")
        for item in detection.evidence:
            console.print(f"  • {item}")
    for warning in plan.preflight.warnings:
        console.print(f"[yellow]Warning:[/yellow] {warning}")
    if plan.preflight.blocking_errors:
        console.print("[red]Migration blocked:[/red]")
        for error in plan.preflight.blocking_errors:
            console.print(f"  • {error}")
        raise typer.Exit(code=1)
    console.print("[green]Preflight passed. No database was modified.[/green]")
    console.print("[bold]Planned stages:[/bold]")
    for action in plan.actions:
        console.print(f"  • {action}")



@app.command("generate-temp-key")
def cmd_generate_temp_key():
    """Generate a one-time temp key for owner setup (create/reset/delete)."""
    generate_temp_key()


@app.command()
def version():
    """Show PasarGuard version."""
    from app import __version__

    console.print(f"[bold blue]PasarGuard[/bold blue] version [bold green]{__version__}[/bold green]")


if __name__ == "__main__":
    app()
