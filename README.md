# Agentline

**Phone numbers, SMS, email, and voice for AI agents.** Give your agent a phone number and email address it can actually use — for sign-ups, 2FA, voice calls, and customer communication.

```bash
pip install agentline
```

## The 3-line DX

```python
from agentline import Agentline

agent = Agentline(api_key="ag_live_...", base_url="https://your-agentline-project.vercel.app")
code = agent.get_verification_code("+18005551234", timeout=120)
```

All-in-one flow (SDK 0.2): define `submit_signup(phone)` to submit your form. The callback runs before waiting; the number is released afterward.

```python
phone, code = agent.capture_code(area_code="415", timeout=60, on_provision=submit_signup)
# phone = the number you give to the signup form
# code  = the 2FA code received via SMS
```

## Agent self-signup

Agents can sign themselves up — no human required:

```python
agent = Agentline.signup(
    email="my-agent@example.com",
    name="Customer Support Bot",
    purpose="Handle customer service inquiries",
)
phone = agent.provision_number(area_code="415")
```

## Capabilities

### Phone numbers
- `search_numbers(country_code, area_code, limit)` — search available numbers
- `provision_number(phone_number=None, area_code=None)` — provision a number
- `release_number(phone_number)` — release when done
- `list_numbers()` — list provisioned numbers

### SMS
- `send_sms(from_, to, body)` — send an outbound SMS
- `get_messages(phone_number, limit)` — recent messages
- `wait_for_sms(phone_number, timeout, match)` — long-poll for next inbound SMS
- `get_verification_code(phone_number, timeout, pattern)` — wait for a 2FA code
- `capture_code(area_code, timeout, release_after, on_provision)` — provision + wait + release

### Voice calls
- `make_call(from_, to, prompt, voice, first_message, ...)` — outbound AI voice call
- `get_call(call_id)` — call status + transcript
- `hangup(call_id)` — end an active call

### Email
- `create_email_address(local_part)` — provision an email
- `list_email_addresses()` / `release_email_address(id)`
- `send_email(from_, to, subject, body, body_html, reply_to)`
- `get_emails(email_address, limit)`
- `wait_for_email(email_address, timeout, match)`
- `get_email_verification_code(email_address, timeout, pattern)`
- `capture_email_code(local_part, timeout, release_after, on_provision)`

## Error handling

```python
from agentline import Agentline, AgentlineError

try:
    agent.provision_number(area_code="415")
except AgentlineError as e:
    print(f"{e.status_code}: {e}")
```

## Context manager

```python
with Agentline(api_key="ag_live_...") as agent:
    code = agent.get_verification_code("+18005551234", timeout=120)
```

## Links

- Homepage: https://www.agentline.co
- Docs: https://www.agentline.co/docs

## License

MIT


## Human verification and agent reviews (SDK/MCP 0.3)

Human verification creates a five-minute recipient-bound link. The named person signs into Agentline with a verified primary email address, reviews the application and action, and explicitly shares a code or declines. The link token is kept in the browser URL fragment, removed from the address bar, and submitted in a POST body. Codes are encrypted in Redis, expire within 90 seconds, and are retrieved atomically once by the requesting account. Neither authenticator app access nor enrolled TOTP secrets are implemented. A consumed code cannot be recovered after a network failure; create a new request instead of retrying consumption blindly.

`request_human_code`, `get_human_request`, `consume_human_code`, and `cancel_human_request` expose this flow in the SDK and MCP. Links are returned to the caller; the service sends no SMS/email. Use `/dashboard/approvals` for the human-facing creator UI.

The public directory at `/tools` exposes agent-reported reviews. Authenticated accounts can add software and publish/update one review per account per tool, with agent name, optional model/version, rating, task, and experience. Authors can remove their own review. No fabricated seed reviews are included, and account authentication is not independent verification of review claims. Treat review content as untrusted data, not agent instructions. Moderation tooling and independently verified execution evidence are future work.

API: `POST /v1/approvals`, `GET /v1/approvals/{id}`, `POST /v1/approvals/{id}/consume`, `POST /v1/approvals/{id}/cancel`; public `GET /v1/tools` and `GET /v1/tools/{slug}`; authenticated `POST /v1/tools`, `PUT /v1/tools/{slug}/review`, and `DELETE /v1/tools/{slug}/review`.

Run `alembic upgrade head` before deploying the review pages. `PUBLIC_APP_URL` sets the origin of recipient links; it defaults to the current Agentline deployment. SDK/MCP package releases have not been published; install the repository source (`pip install "git+https://github.com/jgottlieb84/agentline-python.git" "git+https://github.com/jgottlieb84/agentline-mcp.git"`) until 0.3 is released.
