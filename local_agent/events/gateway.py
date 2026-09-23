"""Event Gateway pipeline: Normalize, Deduplicate, Correlate, and Confidence rating."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import deque
from typing import Any

from local_agent.events.schema import EventClient, EventSource, ObserverType, StandardAgentEvent, StandardEventType
from local_agent.events.store import EventStore


class EventGateway:
    """Processes incoming raw observer events through the 4-step pipeline:
    1. Normalize: Transform unstructured/heterogeneous payloads into SAE format.
    2. Deduplicate: Window-based deduplication against duplicate events from multiple observers.
    3. Correlate: Associate with existing task/session traces and parent event IDs.
    4. Confidence: Adjust event reliability score based on source credibility and cross-validation.
    """

    def __init__(
        self,
        store: EventStore | None = None,
        dedup_window_seconds: float = 5.0,
    ) -> None:
        self.store = store or EventStore(":memory:")
        self.dedup_window_seconds = dedup_window_seconds
        self._lock = threading.Lock()
        # Sliding window buffer: deque of (fingerprint, timestamp)
        self._dedup_history: deque[tuple[str, float]] = deque()
        self._dedup_seen: set[str] = set()
        # Context correlation cache: session_id -> latest_event_id / correlation_id
        self._session_trace: dict[str, str] = {}

    def normalize(self, raw_data: dict[str, Any] | StandardAgentEvent) -> StandardAgentEvent:
        """Step 1: Normalize incoming raw dictionary or event to standard SAE format."""
        if isinstance(raw_data, StandardAgentEvent):
            return raw_data

        # Infer or extract source
        src_raw = raw_data.get("source") or {}
        client = src_raw.get("client") or raw_data.get("client") or EventClient.UNKNOWN
        observer = src_raw.get("observer") or raw_data.get("observer") or ObserverType.LOCAL
        session_id = src_raw.get("session_id") or raw_data.get("session_id") or ""

        # Infer event type
        event_type = raw_data.get("type") or raw_data.get("event_type") or StandardEventType.GENERIC
        if isinstance(event_type, str):
            try:
                event_type = StandardEventType(event_type)
            except ValueError:
                pass

        payload = raw_data.get("payload")
        if payload is None:
            # Gather leftover fields into payload
            reserved = {"event_id", "timestamp", "source", "client", "observer", "session_id", "type", "event_type", "correlation_id", "parent_event_id", "confidence"}
            payload = {k: v for k, v in raw_data.items() if k not in reserved}

        timestamp = float(raw_data.get("timestamp") or time.time())
        correlation_id = str(raw_data.get("correlation_id") or "")
        parent_event_id = str(raw_data.get("parent_event_id") or "")
        confidence = float(raw_data.get("confidence", 1.0))

        event_id = str(raw_data.get("event_id") or "")
        kwargs = {
            "timestamp": timestamp,
            "source": EventSource(client=client, observer=observer, session_id=session_id),
            "type": event_type,
            "payload": payload,
            "correlation_id": correlation_id,
            "parent_event_id": parent_event_id,
            "confidence": confidence,
        }
        if event_id:
            kwargs["event_id"] = event_id

        return StandardAgentEvent(**kwargs)


    def _compute_fingerprint(self, event: StandardAgentEvent) -> str:
        """Compute semantic fingerprint for deduplication."""
        # Key on session, type, and payload content
        src = event.source.to_dict() if isinstance(event.source, EventSource) else event.source
        sess = src.get("session_id", "")
        etype = str(event.type.value if hasattr(event.type, "value") else event.type)
        payload_str = json.dumps(event.payload, sort_keys=True, ensure_ascii=False)
        raw_key = f"{sess}:{etype}:{payload_str}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def deduplicate(self, event: StandardAgentEvent) -> bool:
        """Step 2: Check if event is duplicate within sliding window.
        Returns True if event is UNIQUE (not duplicate), False if duplicate (should be dropped).
        """
        now = event.timestamp
        cutoff = now - self.dedup_window_seconds
        fp = self._compute_fingerprint(event)

        with self._lock:
            # Evict expired entries from deque
            while self._dedup_history and self._dedup_history[0][1] < cutoff:
                old_fp, _ = self._dedup_history.popleft()
                self._dedup_seen.discard(old_fp)

            if fp in self._dedup_seen:
                return False

            self._dedup_seen.add(fp)
            self._dedup_history.append((fp, now))
            return True

    def correlate(self, event: StandardAgentEvent) -> StandardAgentEvent:
        """Step 3: Establish causal links (parent-child) and trace correlation IDs."""
        src = event.source.to_dict() if isinstance(event.source, EventSource) else event.source
        session_id = src.get("session_id", "")

        with self._lock:
            # If correlation_id missing, use or generate session trace
            if not event.correlation_id:
                event.correlation_id = self._session_trace.get(f"corr_{session_id}", f"trace_{session_id or 'default'}")
            else:
                self._session_trace[f"corr_{session_id}"] = event.correlation_id

            # If parent_event_id missing, link to previous event in this session
            if not event.parent_event_id and session_id:
                prev_id = self._session_trace.get(f"last_{session_id}")
                if prev_id and prev_id != event.event_id:
                    event.parent_event_id = prev_id

            if session_id:
                self._session_trace[f"last_{session_id}"] = event.event_id

        return event

    def assess_confidence(self, event: StandardAgentEvent) -> StandardAgentEvent:
        """Step 4: Rate event confidence based on observer reliability and payload verification."""
        src = event.source.to_dict() if isinstance(event.source, EventSource) else event.source
        observer = src.get("observer", "")

        # Baseline confidence weights per observer type:
        # Runtime (0.98) > Native (0.95) > Network (0.90) > Local (0.85)
        observer_baselines = {
            ObserverType.RUNTIME.value: 0.98,
            "runtime_observer": 0.98,
            ObserverType.NATIVE.value: 0.95,
            "native_observer": 0.95,
            ObserverType.NETWORK.value: 0.90,
            "network_observer": 0.90,
            ObserverType.LOCAL.value: 0.85,
            "local_observer": 0.85,
        }

        if observer in observer_baselines:
            score = observer_baselines[observer]
        else:
            score = float(event.confidence)

        # Penalize missing payload or empty dictionary
        if not event.payload:
            score = min(score, 0.5)

        event.confidence = round(score, 2)
        return event


    def ingest(self, raw_data: dict[str, Any] | StandardAgentEvent) -> StandardAgentEvent | None:
        """Ingest event through the complete 4-step pipeline and write to EventStore.
        Returns the saved StandardAgentEvent, or None if deduplicated.
        """
        # 1. Normalize
        event = self.normalize(raw_data)

        # 2. Deduplicate
        if not self.deduplicate(event):
            return None

        # 3. Correlate
        event = self.correlate(event)

        # 4. Confidence
        event = self.assess_confidence(event)

        # Persist
        self.store.append(event)
        return event
