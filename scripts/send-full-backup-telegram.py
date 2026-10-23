import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from app.db import GetDB
from app.services.backup import send_backup_to_telegram


async def main() -> None:
    path = Path(sys.argv[1])
    async with GetDB() as db:
        backup = SimpleNamespace(
            filename=path.name,
            size=path.stat().st_size,
            backup_path=str(path),
            metadata_json={},
        )
        if not await send_backup_to_telegram(db, backup):
            raise RuntimeError("Telegram delivery is not configured or failed")
    print("delivery-ok")


if __name__ == "__main__":
    asyncio.run(main())
