"""Agent hook interface — the bridge to an external AI agent.

An external agent (e.g. a Claude-based monitoring agent) can integrate in
two ways, both local-network by default:

1. Push (webhook): register a URL via POST /api/agent/webhooks. Every new
   event is POSTed there as JSON with URLs the agent can use to inspect
   the snapshot and clip frames. The webhook response may include an
   assessment, or the agent can submit one later.

2. Pull (polling): GET /api/agent/pending returns events that have no
   assessment yet; the agent inspects frames via the frame endpoints and
   submits its verdict with POST /api/agent/assessments.

Agents are instructed (see payload["guidelines"]) to use hedged language
and never claim certainty. Any emergency-style action an agent recommends
still requires explicit user confirmation in the app — assessments are
advisory only.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel, Field

from .models import AgentAssessment, Event

logger = logging.getLogger(__name__)

AGENT_GUIDELINES = (
    "You are assessing home-safety camera events. Never claim certainty: "
    "use phrases like 'possible', 'appears', 'may be'. Recommend, do not act. "
    "Any emergency-style action requires explicit user confirmation."
)


class AgentWebhook(BaseModel):
    name: str
    url: str
    enabled: bool = True


class AgentEventPayload(BaseModel):
    """What an external agent receives for each event."""

    event: Event
    snapshot_url: str | None = None
    frames_url: str | None = None
    assessment_url: str = ""
    guidelines: str = AGENT_GUIDELINES


class AgentHook(ABC):
    """Implement this to receive camera events inside the process.

    Out-of-process agents should use the webhook / polling REST API instead.
    """

    name: str = "base"

    @abstractmethod
    async def on_event(self, payload: AgentEventPayload) -> AgentAssessment | None:
        """Handle an event; optionally return an immediate assessment."""


class LoggingAgentHook(AgentHook):
    """Default in-process hook: just logs. A template for real hooks."""

    name = "logging"

    async def on_event(self, payload: AgentEventPayload) -> AgentAssessment | None:
        logger.info(
            "agent-hook event %s (%s): %s",
            payload.event.id,
            payload.event.type.value,
            payload.event.message,
        )
        return None


class WebhookAgentHook(AgentHook):
    """Forwards events to a registered external webhook URL."""

    def __init__(self, webhook: AgentWebhook, timeout: float = 10.0):
        self.webhook = webhook
        self.name = f"webhook:{webhook.name}"
        self.timeout = timeout

    async def on_event(self, payload: AgentEventPayload) -> AgentAssessment | None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    self.webhook.url, json=payload.model_dump(mode="json")
                )
            if resp.status_code == 200 and resp.content:
                data = resp.json()
                if isinstance(data, dict) and data.get("summary"):
                    data.setdefault("event_id", payload.event.id)
                    data.setdefault("agent_name", self.webhook.name)
                    return AgentAssessment.model_validate(data)
        except Exception as exc:  # never let an agent failure break monitoring
            logger.warning("webhook %s failed: %s", self.webhook.url, exc)
        return None


class AgentGateway:
    """Fans events out to all registered hooks and tracks pending events."""

    def __init__(self, base_url: str = "http://127.0.0.1:8765"):
        self.base_url = base_url
        self.hooks: list[AgentHook] = [LoggingAgentHook()]
        self.webhooks: dict[str, AgentWebhook] = {}
        self._pending: dict[str, Event] = {}  # events awaiting an assessment
        self._max_pending = 200

    def register_hook(self, hook: AgentHook) -> None:
        self.hooks.append(hook)

    def register_webhook(self, webhook: AgentWebhook) -> None:
        self.webhooks[webhook.name] = webhook

    def remove_webhook(self, name: str) -> bool:
        return self.webhooks.pop(name, None) is not None

    def payload_for(self, event: Event) -> AgentEventPayload:
        return AgentEventPayload(
            event=event,
            snapshot_url=(
                f"{self.base_url}/api/events/{event.id}/snapshot.jpg"
                if event.snapshot_path
                else None
            ),
            frames_url=(
                f"{self.base_url}/api/events/{event.id}/frames"
                if event.clip_dir
                else None
            ),
            assessment_url=f"{self.base_url}/api/agent/assessments",
        )

    def pending(self) -> list[Event]:
        return list(self._pending.values())

    def resolve(self, event_id: str) -> None:
        self._pending.pop(event_id, None)

    async def dispatch(self, event: Event) -> list[AgentAssessment]:
        """Send the event to every hook; collect any immediate assessments."""
        self._pending[event.id] = event
        # bound memory: drop oldest pending entries beyond the cap
        while len(self._pending) > self._max_pending:
            self._pending.pop(next(iter(self._pending)))

        payload = self.payload_for(event)
        hooks: list[AgentHook] = list(self.hooks) + [
            WebhookAgentHook(w) for w in self.webhooks.values() if w.enabled
        ]
        results = await asyncio.gather(
            *(h.on_event(payload) for h in hooks), return_exceptions=True
        )
        assessments: list[AgentAssessment] = []
        for hook, result in zip(hooks, results):
            if isinstance(result, AgentAssessment):
                assessments.append(result)
            elif isinstance(result, Exception):
                logger.warning("agent hook %s raised: %s", hook.name, result)
        return assessments
