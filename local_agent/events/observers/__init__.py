"""Observer package exports."""

from local_agent.events.observers.local_observer import LocalObserver
from local_agent.events.observers.proxy_observer import NetworkObserver

__all__ = ["LocalObserver", "NetworkObserver"]
