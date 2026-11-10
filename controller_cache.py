"""Bounded shared read caches with one loader per key and generation.

Only presentation and informational probes use these caches. Model launches,
memory admission, authorization and process safety continue to read live state.
"""
from __future__ import annotations

import copy
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Hashable


@dataclass
class _Flight:
    ready: threading.Event = field(default_factory=threading.Event)
    value: Any = None
    error: BaseException | None = None


class SingleFlightCache:
    """Coalesce concurrent reads, bound storage and return detached snapshots."""

    def __init__(self, ttl_seconds: float, maximum_entries: int = 64,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if ttl_seconds < 0 or maximum_entries < 1:
            raise ValueError("Cache bounds must be nonnegative and storage must be positive.")
        self.ttl_seconds = float(ttl_seconds)
        self.maximum_entries = int(maximum_entries)
        self.clock = clock
        self.lock = threading.Lock()
        self.generation = 0
        self.entries: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self.flights: dict[tuple[int, Hashable], _Flight] = {}
        self.hits = self.loads = self.coalesced = 0

    def clear(self) -> None:
        with self.lock:
            self.generation += 1
            self.entries.clear()

    def get(self, key: Hashable, loader: Callable[[], Any], *, refresh: bool = False) -> Any:
        with self.lock:
            now = self.clock()
            entry = self.entries.get(key)
            if not refresh and entry is not None and now < entry[0]:
                self.hits += 1
                self.entries.move_to_end(key)
                value = entry[1]
                flight = None
                owner = False
            else:
                self.entries.pop(key, None)
                flight_key = (self.generation, key)
                flight = self.flights.get(flight_key)
                owner = flight is None
                if owner:
                    flight = _Flight()
                    self.flights[flight_key] = flight
                    self.loads += 1
                else:
                    self.coalesced += 1
                value = None
        if flight is None:
            return copy.deepcopy(value)
        if owner:
            try:
                flight.value = copy.deepcopy(loader())
                with self.lock:
                    if flight_key[0] == self.generation:
                        self.entries[key] = (self.clock() + self.ttl_seconds, flight.value)
                        self.entries.move_to_end(key)
                        while len(self.entries) > self.maximum_entries:
                            self.entries.popitem(last=False)
            except BaseException as error:
                flight.error = error
            finally:
                with self.lock:
                    self.flights.pop(flight_key, None)
                    flight.ready.set()
        else:
            flight.ready.wait()
        if flight.error is not None:
            raise flight.error
        return copy.deepcopy(flight.value)

    def statistics(self) -> dict[str, int | float]:
        with self.lock:
            return {
                "ttlSeconds": self.ttl_seconds, "entries": len(self.entries),
                "hits": self.hits, "loads": self.loads, "coalesced": self.coalesced,
                "inFlight": len(self.flights),
            }
