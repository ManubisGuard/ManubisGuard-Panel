#!/usr/bin/env python3
"""ManubisGuard CLI."""

from pathlib import Path

import typer

from app.migration.runner import (
    analyze_backup,
    migrate_pasarguard_staging,
    print_json,
    resolve_staging_timescale_version,
    validation_jsonable,
)
from app.migration.staging import StagingDatabase
from app.migration.validator import validate_migrated_database
from cli import console
from cli.admin import generate_temp_key

app = typer.Typer(
    name="ManubisGuard",
    help="ManubisGuard CLI",
    add_completion=False,
    rich_markup_mode="rich",
)


def _env_or(value: str | None, name: str) -> str | None:
    import os

    return value or os.environ.get(name)


@app.command("migrate-check")
def cmd_migrate_check(backup: Path) -> None:
    """Inspect a legacy backup and print the non-destructive migration plan."""
    plan = __import__("app.migration.engine", fromlist=["plan_pasarguard_migration"]).plan_pasarguard_migration(backup)
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


@app.command("migrate-inspect")
def cmd_migrate_inspect(
    backup: Path,
    live_timescale: str | None = typer.Option(None, "--live-timescale"),
    source_timescale: str | None = typer.Option(None, "--source-timescale"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Analyze a PasarGuard backup without touching any database."""
    source_timescale = _env_or(source_timescale, "MANUBISGUARD_MIGRATION_SOURCE_TIMESCALE")
    result = analyze_backup(backup, source_timescale_version=source_timescale)
    payload = {
        "detection": {
            "path": result.detection.path,
            "format": result.detection.format,
            "source_product": result.detection.source_product,
            "confidence": result.detection.confidence,
            "evidence": list(result.detection.evidence),
            "schema_revision": result.detection.schema_revision,
            "source_postgres_major": result.detection.source_postgres_major,
            "warnings": list(result.detection.warnings),
        },
        "preflight": {
            "ok": result.preflight.ok,
            "blocking_errors": list(result.preflight.blocking_errors),
            "warnings": list(result.preflight.warnings),
        },
        "timescale": {
            "versions": list(result.timescale.versions),
            "source_version": result.timescale.source_version,
            "minimum_version": result.timescale.minimum_version,
            "catalog_era": result.timescale.catalog_era,
            "recommended_version": result.timescale.recommended_version,
            "warnings": list(result.timescale.warnings),
        },
        "uses_timescaledb": result.uses_timescaledb,
    }
    if live_timescale:
        try:
            payload["staging_timescale_version"] = resolve_staging_timescale_version(
                result, live_version=live_timescale
            )
        except ValueError as exc:
            payload["staging_timescale_error"] = str(exc)
    if json_output:
        print_json(payload)
        if not result.preflight.ok:
            raise typer.Exit(code=1)
        return
    print_json(payload)
    if not result.preflight.ok:
        raise typer.Exit(code=1)


@app.command("migrate-staging")
def cmd_migrate_staging(
    backup: Path,
    staging_url: str | None = typer.Option(None, "--staging-url"),
    production_url: str | None = typer.Option(None, "--production-url"),
    external_staging: bool = typer.Option(False, "--external-staging"),
    source_timescale: str | None = typer.Option(None, "--source-timescale"),
    timeout: int = typer.Option(900, "--timeout", min=60, max=7200),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Restore a PasarGuard backup into isolated staging, upgrade, normalize and validate."""
    staging_url = _env_or(staging_url, "MANUBISGUARD_MIGRATION_STAGING_URL")
    production_url = _env_or(production_url, "MANUBISGUARD_MIGRATION_PRODUCTION_URL")
    source_timescale = _env_or(source_timescale, "MANUBISGUARD_MIGRATION_SOURCE_TIMESCALE")
    if not staging_url or not production_url:
        raise typer.BadParameter(
            "staging and production URLs must be supplied by option or environment"
        )

    from sqlalchemy.engine import make_url

    staging = StagingDatabase(
        database_name=make_url(staging_url).database or "",
        staging_url=staging_url,
        _production_url=production_url,
    )
    result = migrate_pasarguard_staging(
        backup,
        staging,
        production_url=production_url,
        timeout=timeout,
        allow_external_staging=external_staging,
        source_timescale_version=source_timescale,
    )
    payload = result.as_jsonable()
    if json_output:
        print_json(payload)
    else:
        print_json(payload)
    if not result.valid:
        raise typer.Exit(code=1)


@app.command("migrate-validate")
def cmd_migrate_validate(
    database_url: str | None = typer.Option(None, "--database-url"),
    production_url: str | None = typer.Option(None, "--production-url"),
    external_staging: bool = typer.Option(False, "--external-staging"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Validate an already-restored isolated ManubisGuard database."""
    database_url = _env_or(database_url, "MANUBISGUARD_MIGRATION_DATABASE_URL")
    production_url = _env_or(production_url, "MANUBISGUARD_MIGRATION_PRODUCTION_URL")
    if not database_url:
        raise typer.BadParameter("database URL must be supplied by option or environment")
    if production_url:
        from app.migration.staging import assert_staging_target

        assert_staging_target(
            production_url,
            database_url,
            allow_external_port=external_staging,
        )
    result = validate_migrated_database(database_url)
    payload = validation_jsonable(result)
    print_json(payload) if json_output else print_json(payload)
    if not result.valid:
        raise typer.Exit(code=1)


@app.command("generate-temp-key")
def cmd_generate_temp_key():
    """Generate a one-time temp key for owner setup (create/reset/delete)."""
    generate_temp_key()


@app.command()
def version():
    """Show ManubisGuard version."""
    from app import __version__

    console.print(f"[bold blue]ManubisGuard[/bold blue] version [bold green]{__version__}[/bold green]")


if __name__ == "__main__":
    app()
