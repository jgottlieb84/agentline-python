import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentline import Agentline, AgentlineError


@pytest.mark.parametrize("channel", ["sms", "email"])
def test_long_poll_accepts_backend_routing_field_and_extends_timeout(channel):
    payload = dict(id="1", direction="inbound", extracted_code="123456", created_at="2026-09-08T00:00:00Z", phone_number="routing-key")
    if channel == "sms":
        payload.update(from_number="+15555550101", to_number="+15555550100", body="Code 123456")
    else:
        payload.update(from_email="a@example.com", to_email="b@example.com", subject="Code", body_text="Code 123456")

    def handle(request):
        assert request.url.params["wait"] == "180"
        assert request.extensions["timeout"]["read"] >= 190
        return httpx.Response(200, json={"status": "received", "message": payload})

    with Agentline("test") as client:
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(handle), base_url="https://example.com")
        message = getattr(client, "wait_for_" + channel)("test", timeout=180)
        assert message.extracted_code == "123456"


@pytest.mark.parametrize("channel", ["sms", "email"])
def test_custom_code_pattern_overrides_generic_server_extraction(channel):
    from types import SimpleNamespace
    with Agentline("test") as client:
        message = SimpleNamespace(extracted_code="123456", body="Ticket 123456. Code A3F7BK92", body_text="Ticket 123456. Code A3F7BK92")
        setattr(client, "wait_for_" + channel, lambda *args, **kwargs: message)
        method = client.get_verification_code if channel == "sms" else client.get_email_verification_code
        assert method("test", pattern=r"[A-Z0-9]{8}") == "A3F7BK92"
        assert method("test", pattern=r"X{8}") is None


def test_voice_polling_has_a_deadline(monkeypatch):
    import agentline
    clock = [0.0]
    monkeypatch.setattr(agentline.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(agentline.time, "sleep", lambda delay: clock.__setitem__(0, clock[0] + delay))
    with Agentline("test") as client:
        client._request = lambda *args, **kwargs: {"id": "call-1", "status": "in_progress"}
        with pytest.raises(AgentlineError, match="call-1"):
            client.make_call("from", "to", "prompt", poll_interval=2, wait_timeout=5)
    assert clock[0] == 5


@pytest.mark.parametrize("channel", ["sms", "email"])
def test_capture_exposes_address_before_wait_and_releases_on_failure(channel):
    from types import SimpleNamespace
    events = []
    with Agentline("test") as client:
        client.provision_number = lambda **kw: SimpleNamespace(phone_number="phone")
        client.create_email_address = lambda **kw: SimpleNamespace(email_address="email", id="email-id")
        client.release_number = lambda value: events.append(("release", value))
        client.release_email_address = lambda value: events.append(("release", value))
        def trigger(address):
            events.append(("trigger", address))
            raise RuntimeError("signup failed")
        method = client.capture_code if channel == "sms" else client.capture_email_code
        with pytest.raises(RuntimeError, match="signup failed"):
            method(on_provision=trigger)
    assert events == [("trigger", "phone" if channel == "sms" else "email"), ("release", "phone" if channel == "sms" else "email-id")]


def test_capture_without_trigger_does_not_purchase_number():
    with Agentline("test") as client:
        client.provision_number = lambda **kw: pytest.fail("must not provision")
        with pytest.raises(ValueError, match="on_provision"):
            client.capture_code()
