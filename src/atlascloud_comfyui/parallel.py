"""Concurrent execution for AtlasCloud nodes.

Every AtlasCloud generation node submits a job and then sits inside
``AtlasClient.poll_prediction`` until the render comes back. ComfyUI executes a
prompt graph on a single worker, so N such nodes in one workflow ran strictly
one after another and the wall-clock cost was the *sum* of every render.

ComfyUI can run ``async def`` node functions concurrently: when an async node's
task is not finished yet, the executor parks it (``add_external_block``) and
stages the next ready node instead. This module rewrites every AtlasCloud node
that takes an ``ATLAS_CLIENT`` input into such an async node -- the original
blocking body is pushed onto a worker thread -- so independent Atlas branches of
a workflow fire their POST at roughly the same time and then poll side by side.

Patched nodes also get ``NOT_IDEMPOTENT = True``, which puts the node id into
ComfyUI's cache signature. Without it, several *identical* Atlas nodes in one
graph collapse into a single cache entry and only one of them would really run.
Re-queuing the same workflow still hits the cache, so this does not cause
surprise re-billing.

Environment variables (read live, no restart needed except where noted):

  ATLASCLOUD_PARALLEL             0/false disables the whole patch (restart)
  ATLASCLOUD_MAX_PARALLEL         Atlas jobs in flight at once (default 4)
  ATLASCLOUD_SUBMIT_STAGGER_SEC   min gap between two submissions (default 0.25)
  ATLASCLOUD_SUBMIT_RETRIES       retries on 429/5xx at submit time (default 4)
"""

from __future__ import annotations

import asyncio
import inspect
import os
import random
import time
from typing import Any, Callable, Dict, Optional

_PATCH_FLAG = "_atlascloud_parallel_patched"
_ORIGINAL_ATTR = "__atlascloud_original__"

# Submit-time statuses that are worth another shot: rate limits, and the
# transient gateway errors a burst of concurrent requests tends to provoke.
_RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class _ConcurrencyGate:
    """A resizable semaphore.

    Deliberately not ``asyncio.Semaphore``: the limit is re-read from the
    environment on every acquire, so ATLASCLOUD_MAX_PARALLEL can be tuned while
    ComfyUI is running. Also enforces a small gap between consecutive
    submissions so a wide graph does not hit the API as one burst.
    """

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._event: Optional[asyncio.Event] = None
        self._in_flight = 0
        self._next_start = 0.0

    @staticmethod
    def limit() -> int:
        return max(1, _env_int("ATLASCLOUD_MAX_PARALLEL", 4))

    def _rebind(self) -> asyncio.Event:
        loop = asyncio.get_running_loop()
        if self._event is None or self._loop is not loop:
            # New event loop (ComfyUI restart / test run): the old counter and
            # its waiters belong to a loop that is gone.
            self._loop = loop
            self._event = asyncio.Event()
            self._in_flight = 0
            self._next_start = 0.0
        return self._event

    async def acquire(self) -> None:
        while True:
            event = self._rebind()
            if self._in_flight < self.limit():
                self._in_flight += 1
                break
            # There is no await between the check above and this wait, so a
            # release() cannot slip past us unnoticed.
            await event.wait()

        # Reserve this submission's slot *before* sleeping, otherwise every task
        # that arrives in the same tick computes the same delay and they all
        # wake up together -- which is the burst the stagger exists to prevent.
        stagger = max(0.0, _env_float("ATLASCLOUD_SUBMIT_STAGGER_SEC", 0.25))
        now = time.monotonic()
        slot = max(now, self._next_start)
        self._next_start = slot + stagger
        if slot > now:
            await asyncio.sleep(slot - now)

    def release(self) -> None:
        self._in_flight = max(0, self._in_flight - 1)
        event = self._event
        if event is not None:
            # set() marks every current waiter done synchronously, so the
            # immediate clear() only affects tasks that arrive later.
            event.set()
            event.clear()


_GATE = _ConcurrencyGate()


def _uses_atlas_client(cls: Any) -> bool:
    try:
        spec = cls.INPUT_TYPES()
    except Exception:
        return False
    if not isinstance(spec, dict):
        return False
    for section in ("required", "optional"):
        entries = spec.get(section) or {}
        if not isinstance(entries, dict):
            continue
        for value in entries.values():
            declared = value[0] if isinstance(value, (list, tuple)) and value else value
            if declared == "ATLAS_CLIENT":
                return True
    return False


def _wrap(cls: Any, func_name: str) -> None:
    original: Callable[..., Any] = getattr(cls, func_name)

    async def _atlas_parallel_run(self, *args, **kwargs):
        await _GATE.acquire()
        try:
            # to_thread copies the current context, so ComfyUI's executing-node
            # contextvar (progress bars, previews) still resolves correctly.
            return await asyncio.to_thread(original, self, *args, **kwargs)
        finally:
            _GATE.release()

    _atlas_parallel_run.__name__ = getattr(original, "__name__", func_name)
    _atlas_parallel_run.__qualname__ = getattr(original, "__qualname__", func_name)
    _atlas_parallel_run.__doc__ = getattr(original, "__doc__", None)
    setattr(_atlas_parallel_run, _ORIGINAL_ATTR, original)
    setattr(cls, func_name, _atlas_parallel_run)


def _retry_after_seconds(exc: Exception) -> Optional[float]:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    raw = str(headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


def _patch_submit_retry() -> None:
    """Back off and retry instead of failing a whole node on a 429."""
    from .client.atlas_client import AtlasClient

    if AtlasClient.__dict__.get(_PATCH_FLAG):
        return
    original = AtlasClient._generate

    def _generate_with_retry(self, endpoint: str, payload: Dict[str, Any], *, request_kind: str) -> str:
        attempts = max(0, _env_int("ATLASCLOUD_SUBMIT_RETRIES", 4))
        delay = 2.0
        for attempt in range(attempts + 1):
            try:
                return original(self, endpoint, payload, request_kind=request_kind)
            except Exception as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if attempt >= attempts or status not in _RETRY_STATUS:
                    raise
                wait = _retry_after_seconds(exc)
                if wait is None:
                    wait = delay + random.uniform(0.0, 1.0)
                print(
                    "[AtlasCloud] submit returned HTTP {}; retrying in {:.1f}s ({}/{})".format(
                        status, wait, attempt + 1, attempts
                    )
                )
                time.sleep(wait)
                delay = min(delay * 2.0, 30.0)
        raise RuntimeError("unreachable")  # pragma: no cover

    AtlasClient._generate = _generate_with_retry
    setattr(AtlasClient, _PATCH_FLAG, True)


def enable_parallel(node_class_mappings: Dict[str, Any]) -> int:
    """Make every ATLAS_CLIENT-consuming node in `node_class_mappings` async."""
    if not _env_bool("ATLASCLOUD_PARALLEL", True):
        print("[AtlasCloud] parallel execution disabled via ATLASCLOUD_PARALLEL")
        return 0

    try:
        _patch_submit_retry()
    except Exception as exc:
        print("[AtlasCloud] could not install submit retry:", repr(exc))

    patched = 0
    for name, cls in list((node_class_mappings or {}).items()):
        try:
            func_name = getattr(cls, "FUNCTION", None)
            if not func_name:
                continue
            func = getattr(cls, func_name, None)
            if func is None or inspect.iscoroutinefunction(func):
                continue
            if getattr(func, _ORIGINAL_ATTR, None) is not None:
                continue  # already wrapped, possibly via a base class
            if not _uses_atlas_client(cls):
                continue
            _wrap(cls, func_name)
            # Identical sibling nodes must not share one cache entry.
            cls.NOT_IDEMPOTENT = True
            patched += 1
        except Exception as exc:
            print("[AtlasCloud] could not parallelise {}:".format(name), repr(exc))

    print(
        "[AtlasCloud] parallel execution enabled for {} nodes "
        "(max {} jobs in flight; set ATLASCLOUD_MAX_PARALLEL to change)".format(
            patched, _ConcurrencyGate.limit()
        )
    )
    return patched
