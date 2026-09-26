#!/usr/bin/env python3
"""Manubis CLI"""

import json
from dataclasses import asdict
from typing import Optional

import typer

from cli import console
from cli.admin import generate_temp_key
from app.migration.runner import (
    analyze_backup,
    migrate_manubisguard_staging,
    print_json,
)
from app.migration.staging import MigrationSafetyError
from app.migration.validator import validate_migrated_database

app = typer.Typer(
    name="Manubis",
    help="Manubis CLI",
    add_completion=False,
    rich_markup_mode="rich",
)


@app.command("generate-temp-key")
def cmd_generate_temp_key():
    """Generate a one-time temp key for owner setup (create/reset/delete)."""
    generate_temp_key()


@app.command("migrate-inspect")
def migrate_inspect(
    backup: str,
    live_timescale: Optional[str] = typer.Option(None, "--live-timescale"),
    source_timescale: Optional[str] = typer.Option(None, "--source-timescale"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Inspect a backup without restoring or touching production."""
    try:
        analysis = analyze_backup(backup, source_timescale_version=source_timescale)
        staging_timescale_error = None
        if analysis.uses_timescaledb and live_timescale:
            from app.migration.runner import resolve_staging_timescale_version
            try:
                resolve_staging_timescale_version(analysis, live_version=live_timescale)
            except Exception as exc:
                staging_timescale_error = str(exc)
        payload = {
            "detection": asdict(analysis.detection),
            "preflight": analysis.preflight.as_jsonable(),
            "timescale": asdict(analysis.timescale),
            "uses_timescaledb": analysis.uses_timescaledb,
            "staging_timescale_error": staging_timescale_error,
        }
        if json_output:
            print_json(payload)
        else:
            console.print(json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception as exc:
        if json_output:
            raise typer.Exit(code=1) from exc
        raise typer.BadParameter(str(exc)) from exc


@app.command("migrate-staging")
def migrate_staging(
    backup: str,
    external_staging: bool = typer.Option(False, "--external-staging"),
    source_timescale: Optional[str] = typer.Option(None, "--source-timescale"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Restore and migrate a backup into an isolated staging database."""
    import os

    staging_url = os.environ.get("MANUBISGUARD_MIGRATION_STAGING_URL", "").strip()
    production_url = os.environ.get("MANUBISGUARD_MIGRATION_PRODUCTION_URL", "").strip()
    if not staging_url or not production_url:
        raise typer.BadParameter("Migration staging and production URLs must be provided by the host orchestrator.")
    try:
        from app.migration.staging import StagingDatabase
        staging = StagingDatabase(
            database_name=staging_url.rsplit("/", 1)[-1].split("?", 1)[0],
            staging_url=staging_url,
            _production_url=production_url,
        )
        result = migrate_manubisguard_staging(
            backup,
            staging,
            production_url=production_url,
            allow_external_staging=external_staging,
            source_timescale_version=source_timescale,
        )
        payload = result.as_jsonable()
        if json_output:
            print_json(payload)
        else:
            console.print(json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception as exc:
        if json_output:
            print(str(exc))
            raise typer.Exit(code=1) from exc
        raise typer.BadParameter(str(exc)) from exc


@app.command("migrate-validate")
def migrate_validate(
    database_url: str = typer.Option(..., "--database-url"),
    production_url: Optional[str] = typer.Option(None, "--production-url"),
    external_staging: bool = typer.Option(False, "--external-staging"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Validate an isolated migrated database without modifying it."""
    result = validate_migrated_database(database_url)
    payload = {
        "valid": result.valid,
        "blocking_errors": list(result.blocking_errors),
        "warnings": list(result.warnings),
        "missing_target_tables": list(result.missing_target_tables),
        "orphan_checks": [asdict(item) for item in result.orphan_checks],
    }
    if json_output:
        print_json(payload)
    else:
        console.print(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command()
def version():
    """Show Manubis version."""
    from app import __version__

    console.print(f"[bold blue]Manubis[/bold blue] version [bold green]{__version__}[/bold green]")


if __name__ == "__main__":
    app()