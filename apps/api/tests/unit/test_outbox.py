"""
Unit Tests for Outbox and Event Bus.
"""

import uuid

import pytest

from apps.api.app.platform.events.bus import EventBus
from apps.api.app.platform.events.outbox import OutboxEvent, OutboxStatus


def test_outbox_model_initialization():
    """Verify default attributes and status of an outbox event."""
    t_id = uuid.uuid4()
    event = OutboxEvent(
        tenant_id=t_id,
        event_type="content.document_created",
        aggregate_type="Document",
        aggregate_id="doc_12345",
        payload={"name": "AnnualReport.pdf", "size": 1048576},
        correlation_id="corr_98765",
    )
    assert event.status == OutboxStatus.PENDING
    assert event.schema_version == "1.0.0"
    assert event.retry_count == 0
    assert event.payload["name"] == "AnnualReport.pdf"


@pytest.mark.asyncio
async def test_event_bus_dispatch():
    """Verify that events are received by subscribers and errors isolated."""
    bus = EventBus()
    received = []

    async def sample_handler(payload):
        received.append(payload["msg"])

    async def failing_handler(payload):
        raise RuntimeError("Deliberate failure in test subscriber")

    bus.subscribe("test.event", sample_handler)
    bus.subscribe("test.event", failing_handler)

    # Dispatching must not raise even if one handler fails
    await bus.publish("test.event", {"msg": "hello_world"})
    assert received == ["hello_world"]
