"""How AgentProof talks to each kind of agent."""

from agentproof.adapters.base import (
    AgentAdapter,
    AgentSession,
    AgentTurn,
    UnsupportedSetupError,
)

__all__ = ["AgentAdapter", "AgentSession", "AgentTurn", "UnsupportedSetupError"]
