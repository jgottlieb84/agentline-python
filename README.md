# Agentline

**Phone numbers, SMS, email, and voice for AI agents.** Give your agent a phone number and email address it can actually use — for sign-ups, 2FA, voice calls, and customer communication.

```bash
pip install agentline
```

## The 3-line DX

```python
from agentline import Agentline

agent = Agentline(api_key="ag_live_...")
code = agent.get_verification_code("+18005551234", timeout=120)
```

All-in-one flow:

```python
phone, code = agent.capture_code(area_code="415", timeout=60)
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
- `capture_code(area_code, timeout, release_after)` — provision + wait + release

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
- `capture_email_code(local_part, timeout, release_after)`

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
