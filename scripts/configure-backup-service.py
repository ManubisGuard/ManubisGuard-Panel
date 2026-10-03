from __future__ import annotations
import asyncio
import json
import sys
from app.db import GetDB
from app.services.backup import configure_backup_schedule, configure_telegram

async def main() -> None:
    payload = json.load(sys.stdin)
    async with GetDB() as db:
        if payload.get("telegram_bot_token"):
            await configure_telegram(db, created_by=None, token=payload["telegram_bot_token"], chat_id=str(payload["telegram_chat_id"]))
        await configure_backup_schedule(
            db,
            enabled=True,
            frequency=payload["frequency"],
            interval_minutes=payload.get("interval_minutes"),
            hour=payload.get("hour", 2),
            minute=payload.get("minute", 0),
            weekday=payload.get("weekday"),
            day_of_month=payload.get("day_of_month"),
            retention_count=payload.get("retention_count", 7),
        )
        print("Backup service configured.")

if __name__ == "__main__":
    asyncio.run(main())
