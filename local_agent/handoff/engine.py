"""Handoff Engine: profiles target agents, adapts ContextPackage into target protocols, and dispatches handoffs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable

from local_agent.events.schema import EventClient, StandardAgentEvent, StandardEventType
from local_agent.events.store import EventStore
from local_agent.transformation.context_package import ContextPackage


class PromptProtocol(str, Enum):
    MARKDOWN = "markdown"              # Structured system/user markdown prompt
    OPENAI_TOOLS = "openai_tools"      # Function calling schema payload
    CLAUDE_XML = "claude_xml"          # Anthropic style <context>...</context> XML tags
    LOCAL_AGENT = "local_agent"        # AgentForge local-agent task payload


@dataclass
class TargetAgentProfile:
    agent_id: str
    name: str
    context_window_limit: int = 128_000
    protocol: PromptProtocol = PromptProtocol.MARKDOWN
    specialty: str = "general_coding"  # e.g., "test_repair", "refactoring"
    model_name: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "context_window_limit": self.context_window_limit,
            "protocol": self.protocol.value,
            "specialty": self.specialty,
            "model_name": self.model_name,
        }


@dataclass
class HandoffPayload:
    handoff_id: str
    target_agent_id: str
    protocol: PromptProtocol
    formatted_context: str | dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


class HandoffEngine:
    """Routes and formats context packages for specific target execution agents."""

    def __init__(self, store: EventStore | None = None) -> None:
        self.store = store
        self._registry: dict[str, TargetAgentProfile] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(
            TargetAgentProfile(
                agent_id="local_executor",
                name="AgentForge Local Executor",
                context_window_limit=64_000,
                protocol=PromptProtocol.LOCAL_AGENT,
                specialty="local_coding_and_testing",
            )
        )
        self.register(
            TargetAgentProfile(
                agent_id="claude_specialist",
                name="Claude 3.5 Sonnet Specialist",
                context_window_limit=200_000,
                protocol=PromptProtocol.CLAUDE_XML,
                specialty="complex_architecture_refactor",
            )
        )
        self.register(
            TargetAgentProfile(
                agent_id="deepseek_coder",
                name="DeepSeek Coder Reasoning",
                context_window_limit=64_000,
                protocol=PromptProtocol.MARKDOWN,
                specialty="fast_bug_fixing",
            )
        )

    def register(self, profile: TargetAgentProfile) -> None:
        self._registry[profile.agent_id] = profile

    def get_profile(self, agent_id: str) -> TargetAgentProfile | None:
        return self._registry.get(agent_id)

    def prepare_handoff(
        self,
        package: ContextPackage,
        target_agent_id: str,
        task_instruction: str = "Continue and complete the coding task",
    ) -> HandoffPayload:
        profile = self._registry.get(target_agent_id)
        if not profile:
            profile = TargetAgentProfile(
                agent_id=target_agent_id,
                name=target_agent_id,
                protocol=PromptProtocol.MARKDOWN,
            )

        # Adapt package to protocol
        if profile.protocol == PromptProtocol.LOCAL_AGENT:
            # Format compatible with local_agent.mcp.tools.execute payload
            formatted: str | dict[str, Any] = {
                "task": f"{task_instruction}\n\nContext Package Reason: {package.provenance.reason_for_package}",
                "workspace": package.snapshot.workspace_path if package.snapshot else ".",
                "package_id": package.package_id,
                "modified_files": package.snapshot.modified_files if package.snapshot else [],
            }
        elif profile.protocol == PromptProtocol.CLAUDE_XML:
            formatted = f"""<context_package id="{package.package_id}">
<snapshot git_head="{package.snapshot.git_head if package.snapshot else ''}">
{json.dumps(package.snapshot.to_dict() if package.snapshot else {}, indent=2)}
</snapshot>
<git_diff>
{package.diff}
</git_diff>
<task>
{task_instruction}
</task>
</context_package>"""
        else:
            # Markdown prompt default
            formatted = f"""{package.to_markdown()}

---
## Assigned Task
{task_instruction}
"""

        handoff_id = f"ho_{package.package_id}"

        # Record handoff event in EventStore if available
        if self.store:
            from local_agent.events.schema import EventSource, ObserverType

            self.store.append(
                StandardAgentEvent(
                    source=EventSource(
                        client=package.provenance.initiating_client,
                        observer=ObserverType.LOCAL,
                        session_id=package.package_id,
                    ),
                    type=StandardEventType.HANDOFF_TRIGGERED,
                    payload={
                        "handoff_id": handoff_id,
                        "target_agent_id": target_agent_id,
                        "protocol": profile.protocol.value,
                        "package_id": package.package_id,
                    },
                    correlation_id=package.provenance.trace_id,
                )
            )


        return HandoffPayload(
            handoff_id=handoff_id,
            target_agent_id=target_agent_id,
            protocol=profile.protocol,
            formatted_context=formatted,
            metadata={
                "package_id": package.package_id,
                "trace_id": package.provenance.trace_id,
            },
        )
