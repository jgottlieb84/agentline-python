"""Agentline Python SDK.

The developer-facing package — provision a number and capture a 2FA code
in three lines of code:

    from agentline import Agentline
    agent = Agentline(api_key="ag_live_...")
    code = agent.get_verification_code("+18005551234", timeout=120)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx


__version__ = "0.1.0"

__all__ = [
    "Agentline",
    "AgentlineError",
    "SMSMessage",
    "PhoneNumber",
    "CallResult",
    "EmailAddress",
    "EmailMessageResult",
]

DEFAULT_BASE_URL = "https://api.agentline.dev"
DEFAULT_TIMEOUT = 120.0


@dataclass
class SMSMessage:
    """A single SMS message."""
    id: str
    direction: str
    from_number: str
    to_number: str
    body: str
    extracted_code: str | None
    created_at: str


@dataclass
class PhoneNumber:
    """A provisioned phone number."""
    id: str
    phone_number: str
    provider: str
    status: str


@dataclass
class CallResult:
    """Result of a voice call."""
    id: str
    status: str
    from_number: str
    to_number: str
    duration_seconds: float | None = None
    transcript: list[dict] | None = None
    summary: str | None = None


@dataclass
class EmailAddress:
    """A provisioned email address."""
    id: str
    email_address: str
    provider: str
    status: str


@dataclass
class EmailMessageResult:
    """A single email message."""
    id: str
    direction: str
    from_email: str
    to_email: str
    subject: str
    body_text: str
    extracted_code: str | None
    created_at: str


class AgentlineError(Exception):
    """Base exception for Agentline SDK errors."""

    def __init__(self, message: str, status_code: int | None = None, response: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class Agentline:
    """Agentline client — phone numbers & SMS for AI agents.

    Usage::

        from agentline import Agentline

        # Option 1: Use an existing API key
        agent = Agentline(api_key="ag_live_...")

        # Option 2: Self-signup as an autonomous agent
        agent = Agentline.signup(email="my-agent@example.com", name="My Agent")
        print(f"My API key: {agent.api_key}")

        # Provision a number
        number = agent.provision_number(area_code="415")

        # Wait for a 2FA code (blocks until received or timeout)
        code = agent.get_verification_code(number.phone_number, timeout=120)
        print(f"Got code: {code}")

        # Send an SMS
        agent.send_sms(from_=number.phone_number, to="+15551234567", body="Hello!")

        # Release when done
        agent.release_number(number.phone_number)
    """

    @classmethod
    def signup(
        cls,
        email: str,
        name: str | None = None,
        purpose: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> "Agentline":
        """Create a new Agentline account autonomously and return a ready client.

        No human required — agents can sign up themselves.
        Rate-limited to 5 signups per IP per hour.

        Returns:
            A configured Agentline instance with the new API key.

        Usage::

            agent = Agentline.signup(
                email="my-agent@example.com",
                name="Customer Support Bot",
                purpose="Handle customer service inquiries",
            )
            phone = agent.provision_number(area_code="415")
        """
        with httpx.Client(base_url=base_url, timeout=30.0) as client:
            payload: dict[str, Any] = {"email": email}
            if name:
                payload["name"] = name
            if purpose:
                payload["purpose"] = purpose
            resp = client.post("/v1/signup", json=payload)
            if resp.status_code >= 400:
                raise AgentlineError(
                    f"Signup failed: {resp.status_code} {resp.text}",
                    status_code=resp.status_code,
                )
            data = resp.json()
        return cls(api_key=data["api_key"], base_url=base_url)

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key  # public so users can grab it after signup
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout + 10,  # buffer above long-poll timeout
        )

    # ── Number management ────────────────────────────────────────────

    def search_numbers(
        self,
        country_code: str = "US",
        area_code: str | None = None,
        limit: int = 5,
    ) -> list[str]:
        """Search for available phone numbers."""
        params: dict[str, Any] = {"country_code": country_code, "limit": limit}
        if area_code:
            params["area_code"] = area_code

        resp = self._request("GET", "/v1/numbers/search", params=params)
        return resp["available"]

    def provision_number(
        self,
        phone_number: str | None = None,
        area_code: str | None = None,
        country_code: str = "US",
    ) -> PhoneNumber:
        """Provision a phone number.

        If *phone_number* is not given, searches for an available number
        (optionally filtered by *area_code*) and provisions the first result.
        """
        if not phone_number:
            available = self.search_numbers(country_code=country_code, area_code=area_code, limit=1)
            if not available:
                raise AgentlineError("No numbers available for the requested criteria")
            phone_number = available[0]

        resp = self._request("POST", "/v1/numbers", json={"phone_number": phone_number})
        return PhoneNumber(
            id=resp["id"],
            phone_number=resp["phone_number"],
            provider=resp["provider"],
            status=resp["status"],
        )

    def release_number(self, phone_number: str) -> bool:
        """Release a provisioned number."""
        resp = self._request("DELETE", f"/v1/numbers/{phone_number}")
        return resp.get("status") == "released"

    def list_numbers(self) -> list[PhoneNumber]:
        """List all provisioned numbers."""
        resp = self._request("GET", "/v1/numbers")
        return [
            PhoneNumber(id=n["id"], phone_number=n["phone_number"], provider=n["provider"], status="active")
            for n in resp["numbers"]
        ]

    # ── Messages ─────────────────────────────────────────────────────

    def get_messages(self, phone_number: str, limit: int = 20) -> list[SMSMessage]:
        """Retrieve recent messages for a phone number."""
        resp = self._request("GET", f"/v1/messages/{phone_number}", params={"limit": limit})
        return [SMSMessage(**m) for m in resp["messages"]]

    def send_sms(self, from_: str, to: str, body: str) -> dict:
        """Send an outbound SMS."""
        return self._request("POST", "/v1/messages/send", json={
            "from_number": from_,
            "to_number": to,
            "body": body,
        })

    # ── 2FA / Verification code capture ──────────────────────────────

    def wait_for_sms(
        self,
        phone_number: str,
        timeout: float = 120.0,
        match: str | None = None,
    ) -> SMSMessage | None:
        """Long-poll for the next inbound SMS on *phone_number*.

        Args:
            phone_number: The provisioned number to listen on.
            timeout: Max seconds to wait.
            match: Optional regex pattern to filter messages.

        Returns:
            The matching SMSMessage, or None on timeout.
        """
        params: dict[str, Any] = {"wait": timeout}
        if match:
            params["match"] = match

        resp = self._request("GET", f"/v1/messages/{phone_number}", params=params)
        if resp.get("status") == "timeout" or resp.get("message") is None:
            return None
        return SMSMessage(**resp["message"])

    def get_verification_code(
        self,
        phone_number: str,
        timeout: float = 120.0,
        pattern: str = r"\d{4,8}",
    ) -> str | None:
        """Wait for and return a verification code. The killer one-liner.

        Args:
            phone_number: The provisioned number expecting a code.
            timeout: Max seconds to wait.
            pattern: Regex for the code format (default: 4-8 digit number).

        Returns:
            The extracted code string, or None on timeout.
        """
        msg = self.wait_for_sms(phone_number, timeout=timeout, match=pattern)
        if msg and msg.extracted_code:
            return msg.extracted_code
        if msg and msg.body:
            # Fallback: try to extract from body client-side
            m = re.search(pattern, msg.body)
            return m.group(0) if m else msg.body
        return None

    # ── Convenience: provision + capture + release ───────────────────

    def capture_code(
        self,
        area_code: str | None = None,
        timeout: float = 120.0,
        release_after: bool = True,
    ) -> tuple[str, str | None]:
        """All-in-one: provision a number, wait for a code, optionally release.

        Returns:
            (phone_number, code) tuple.

        Usage::

            phone, code = agent.capture_code(area_code="415", timeout=60)
            # Use `phone` as the phone number for signup
            # `code` is the 2FA code received via SMS
        """
        number = self.provision_number(area_code=area_code)
        try:
            code = self.get_verification_code(number.phone_number, timeout=timeout)
            return number.phone_number, code
        finally:
            if release_after:
                self.release_number(number.phone_number)

    # ── Voice calls ──────────────────────────────────────────────────

    def make_call(
        self,
        from_: str,
        to: str,
        prompt: str,
        voice: str = "aura-asteria-en",
        first_message: str | None = None,
        llm_model: str = "claude-sonnet-4-20250514",
        max_duration_seconds: int = 300,
        wait: bool = True,
        poll_interval: float = 2.0,
    ) -> "CallResult":
        """Place an outbound AI voice call.

        Args:
            from_: Your provisioned phone number.
            to: The number to call.
            prompt: System prompt for the AI voice agent.
            voice: Deepgram TTS voice (e.g. "aura-asteria-en", "aura-orion-en").
            first_message: What the AI says when the call connects.
            llm_model: Claude model for conversation.
            max_duration_seconds: Max call duration.
            wait: If True, blocks until call completes and returns transcript.
            poll_interval: Seconds between status polls when wait=True.

        Returns:
            CallResult with status, transcript, and summary.

        Usage::

            result = agent.make_call(
                from_="+18005551234",
                to="+15551234567",
                prompt="You are a medical records coordinator...",
                first_message="Hi, this is Sarah from Dr. Smith's office.",
            )
            print(result.transcript)
        """
        resp = self._request("POST", "/v1/calls", json={
            "from_number": from_,
            "to_number": to,
            "prompt": prompt,
            "voice": voice,
            "first_message": first_message,
            "llm_model": llm_model,
            "max_duration_seconds": max_duration_seconds,
        })

        call_id = resp["id"]

        if not wait:
            return CallResult(
                id=call_id,
                status=resp["status"],
                from_number=from_,
                to_number=to,
            )

        # Poll until call completes
        import time as _time
        terminal_states = {"completed", "failed", "no_answer", "busy"}

        while True:
            _time.sleep(poll_interval)
            status = self._request("GET", f"/v1/calls/{call_id}")

            if status["status"] in terminal_states:
                return CallResult(
                    id=call_id,
                    status=status["status"],
                    from_number=from_,
                    to_number=to,
                    duration_seconds=status.get("duration_seconds"),
                    transcript=status.get("transcript"),
                    summary=status.get("summary"),
                )

    def get_call(self, call_id: str) -> "CallResult":
        """Get the status and transcript of a call."""
        status = self._request("GET", f"/v1/calls/{call_id}")
        return CallResult(
            id=call_id,
            status=status["status"],
            from_number=status["from_number"],
            to_number=status["to_number"],
            duration_seconds=status.get("duration_seconds"),
            transcript=status.get("transcript"),
            summary=status.get("summary"),
        )

    def hangup(self, call_id: str) -> dict:
        """Hang up an active call."""
        return self._request("POST", f"/v1/calls/{call_id}/hangup")

    # ── Email addresses ───────────────────────────────────────────────

    def create_email_address(self, local_part: str | None = None) -> EmailAddress:
        """Create a new email address for sending/receiving.

        Args:
            local_part: Optional local part (e.g. "my-agent"). Auto-generated if omitted.

        Returns:
            EmailAddress with the provisioned address.

        Usage::

            email = agent.create_email_address()
            print(email.email_address)  # "agent-a1b2c3d4@mail.agentline.co"
        """
        body: dict[str, Any] = {}
        if local_part:
            body["local_part"] = local_part

        resp = self._request("POST", "/v1/emails/addresses", json=body)
        return EmailAddress(
            id=resp["id"],
            email_address=resp["email_address"],
            provider=resp["provider"],
            status=resp["status"],
        )

    def list_email_addresses(self) -> list[EmailAddress]:
        """List all provisioned email addresses."""
        resp = self._request("GET", "/v1/emails/addresses")
        return [
            EmailAddress(id=a["id"], email_address=a["email_address"], provider=a["provider"], status="active")
            for a in resp["addresses"]
        ]

    def release_email_address(self, address_id: str) -> bool:
        """Release a provisioned email address."""
        resp = self._request("DELETE", f"/v1/emails/addresses/{address_id}")
        return resp.get("status") == "released"

    # ── Email messages ──────────────────────────────────────────────

    def send_email(
        self,
        from_: str,
        to: str,
        subject: str,
        body: str,
        body_html: str | None = None,
        reply_to: str | None = None,
    ) -> dict:
        """Send an outbound email."""
        payload: dict[str, Any] = {
            "from_email": from_,
            "to_email": to,
            "subject": subject,
            "body": body,
        }
        if body_html:
            payload["body_html"] = body_html
        if reply_to:
            payload["reply_to"] = reply_to

        return self._request("POST", "/v1/emails/send", json=payload)

    def get_emails(self, email_address: str, limit: int = 20) -> list[EmailMessageResult]:
        """Retrieve recent emails for an address."""
        resp = self._request("GET", f"/v1/emails/{email_address}", params={"limit": limit})
        return [EmailMessageResult(**m) for m in resp["messages"]]

    def wait_for_email(
        self,
        email_address: str,
        timeout: float = 120.0,
        match: str | None = None,
    ) -> EmailMessageResult | None:
        """Long-poll for the next inbound email.

        Args:
            email_address: The provisioned address to listen on.
            timeout: Max seconds to wait.
            match: Optional regex pattern to filter.

        Returns:
            The matching EmailMessageResult, or None on timeout.
        """
        params: dict[str, Any] = {"wait": timeout}
        if match:
            params["match"] = match

        resp = self._request("GET", f"/v1/emails/{email_address}", params=params)
        if resp.get("status") == "timeout" or resp.get("message") is None:
            return None
        return EmailMessageResult(**resp["message"])

    def get_email_verification_code(
        self,
        email_address: str,
        timeout: float = 120.0,
        pattern: str = r"\d{4,8}",
    ) -> str | None:
        """Wait for and return a verification code from email.

        Args:
            email_address: The provisioned address expecting a code.
            timeout: Max seconds to wait.
            pattern: Regex for the code format (default: 4-8 digit number).

        Returns:
            The extracted code string, or None on timeout.
        """
        msg = self.wait_for_email(email_address, timeout=timeout, match=pattern)
        if msg and msg.extracted_code:
            return msg.extracted_code
        if msg and msg.body_text:
            m = re.search(pattern, msg.body_text)
            return m.group(0) if m else msg.body_text
        return None

    def capture_email_code(
        self,
        local_part: str | None = None,
        timeout: float = 120.0,
        release_after: bool = True,
    ) -> tuple[str, str | None]:
        """All-in-one: create email address, wait for a code, optionally release.

        Returns:
            (email_address, code) tuple.

        Usage::

            email, code = agent.capture_email_code(timeout=60)
            # Use `email` for signup
            # `code` is the verification code received via email
        """
        addr = self.create_email_address(local_part=local_part)
        try:
            code = self.get_email_verification_code(addr.email_address, timeout=timeout)
            return addr.email_address, code
        finally:
            if release_after:
                self.release_email_address(addr.id)

    # ── Internal ─────────────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs) -> dict:
        resp = self._client.request(method, path, **kwargs)
        if resp.status_code >= 400:
            raise AgentlineError(
                f"API error {resp.status_code}: {resp.text}",
                status_code=resp.status_code,
                response=resp,
            )
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
