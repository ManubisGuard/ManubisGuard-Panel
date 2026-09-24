from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import asyncpg

from app.migration.compatibility import TimescaleCompatibility, analyze_timescale_sql, version_tuple

# TimescaleDB metadata queries deliberately use only public/user-facing metadata.
HYPERTABLES_QUERY = """...
"""
