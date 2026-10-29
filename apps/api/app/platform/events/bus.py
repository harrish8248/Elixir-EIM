"""
Internal Event Bus for In-Memory Asynchronous Message Dispatching.
"""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from apps.api.app.platform.logging import logger

EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    """
    Publish/Subscribe event bus for decoupled inter-module messaging.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, set[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for a given event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = set()
        self._subscribers[event_type].add(handler)
        logger.debug(f"Subscribed handler '{handler.__name__}' to '{event_type}'")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a previously registered handler."""
        if event_type in self._subscribers:
            self._subscribers[event_type].discard(handler)

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """
        Dispatch an event to all registered subscribers concurrently.
        Failures in one handler do not abort execution of other handlers.
        """
        handlers = list(self._subscribers.get(event_type, []))
        # Support wildcard topic subscription e.g. "content.*"
        wildcard_topic = event_type.split(".")[0] + ".*"
        handlers.extend(list(self._subscribers.get(wildcard_topic, [])))

        if not handlers:
            logger.debug(f"No active subscribers for event '{event_type}'")
            return

        tasks = [self._safe_execute(handler, event_type, payload) for handler in handlers]
        await asyncio.gather(*tasks)

    async def _safe_execute(
        self, handler: EventHandler, event_type: str, payload: dict[str, Any]
    ) -> None:
        try:
            await handler(payload)
        except Exception as exc:
            logger.error(
                f"Handler '{handler.__name__}' failed while processing '{event_type}': {exc}",
                exc_info=True,
            )


# Global platform event bus singleton
event_bus: EventBus = EventBus()
