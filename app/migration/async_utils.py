from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Coroutine


def run_sync_in_worker[T](func, *args, **kwargs) -> T:
    """Run synchronous code in a worker thread when called from an active event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return func(*args, **kwargs)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="mg-migration-sync") as pool:
        return pool.submit(func, *args, **kwargs).result()


def run_async[T](coro: Coroutine[object, object, T]) -> T:
    """Run a coroutine from sync code, including when the caller already has a loop.

    The migration/validation helpers are intentionally synchronous at their public
    boundary because they are used by CLI commands and installer helpers. When a
    caller already runs inside an asyncio loop, execute the coroutine in a short-lived
    worker thread instead of nesting asyncio.run().
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="mg-migration") as pool:
        return pool.submit(asyncio.run, coro).result()
