"""Small tqdm wrapper with a no-dependency text fallback."""

from __future__ import annotations

import sys
import time
from collections.abc import Iterable, Iterator
from typing import Any


try:
    from tqdm import tqdm as _tqdm
except ImportError:  # pragma: no cover - used only on installations without tqdm
    _tqdm = None


class _TextProgress:
    """Minimal progress reporter used only when tqdm is unavailable."""

    def __init__(
        self,
        iterable: Iterable[Any] | None = None,
        *,
        total: int | None = None,
        desc: str = "Progress",
        unit: str = "item",
        disable: bool = False,
        **_: Any,
    ) -> None:
        self.iterable = iterable
        self.total = total if total is not None else (len(iterable) if hasattr(iterable, "__len__") else None)
        self.desc = desc
        self.unit = unit
        self.disable = disable
        self.count = 0
        self.started = time.monotonic()
        self.next_report = 0.0
        self._report(force=True)

    def __enter__(self) -> "_TextProgress":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def __iter__(self) -> Iterator[Any]:
        if self.iterable is None:
            return
        for item in self.iterable:
            yield item
            self.update(1)

    def set_description(self, desc: str, refresh: bool = True) -> None:
        self.desc = desc
        if refresh:
            self._report(force=True)

    def update(self, amount: int = 1) -> None:
        self.count += amount
        self._report()

    def close(self) -> None:
        self._report(force=True)

    def _report(self, force: bool = False) -> None:
        if self.disable:
            return
        if self.total:
            fraction = min(1.0, self.count / self.total)
            if not force and fraction < self.next_report:
                return
            self.next_report = fraction + 0.05
            elapsed = time.monotonic() - self.started
            rate = self.count / elapsed if elapsed > 0.0 else 0.0
            remaining = (self.total - self.count) / rate if rate > 0.0 else float("nan")
            eta = f", ETA {remaining:,.0f}s" if remaining == remaining else ""
            message = f"{self.desc}: {self.count}/{self.total} {self.unit} ({fraction:6.1%}){eta}"
        else:
            message = f"{self.desc}: {self.count} {self.unit}"
        print(message, file=sys.stderr, flush=True)


def progress(*args: Any, **kwargs: Any) -> Any:
    """Return tqdm when installed, otherwise a basic percentage reporter."""
    if _tqdm is not None:
        kwargs.setdefault("dynamic_ncols", True)
        kwargs.setdefault("mininterval", 0.2)
        return _tqdm(*args, **kwargs)
    return _TextProgress(*args, **kwargs)
