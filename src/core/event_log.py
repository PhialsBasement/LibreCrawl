"""In-memory change journal for live crawl data.

Every mutation to crawl data (new URL result, updated URL result, new link,
link status change, new issue) is recorded as an event with a monotonically
increasing sequence number. The web UI polls with the last sequence it has
seen and receives only what changed since — including updates to rows it
already holds, which count-based array slicing could never deliver.

An epoch identifies one generation of data. Starting a new crawl, loading a
saved crawl, or resuming from the database begins a new epoch; a client
presenting a stale epoch gets `reset` and the full event stream from zero.

Events hold references to the live dicts rather than copies. A dict mutated
after emission serializes with its newest values, which is harmless because
every mutation also emits an update event.
"""
import threading
import uuid


class CrawlEventLog:
    def __init__(self):
        self._lock = threading.Lock()
        self._events = []
        self.epoch = uuid.uuid4().hex

    def new_epoch(self):
        """Start a new data generation, discarding all recorded events."""
        with self._lock:
            self._events = []
            self.epoch = uuid.uuid4().hex

    def emit(self, kind, data):
        with self._lock:
            self._events.append({'kind': kind, 'data': data})

    def emit_many(self, kind, items):
        with self._lock:
            for item in items:
                self._events.append({'kind': kind, 'data': item})

    def events_since(self, seq, epoch):
        """Return (reset, events, latest_seq, epoch).

        Sequence numbers are indexes into the event list, so "since seq N"
        is the slice events[N:]. A mismatched epoch resets the client: it
        gets every event from zero and must discard its accumulated state.
        """
        with self._lock:
            reset = epoch != self.epoch
            start = 0 if reset else max(0, min(seq, len(self._events)))
            return reset, self._events[start:], len(self._events), self.epoch
