"""State transition model for StateMachine engine."""

from typing import Callable, Any, Awaitable, Optional
from dataclasses import dataclass


@dataclass
class StateTransition:
    """Represents a transition between two states with optional guard and action."""

    from_state: Any
    to_state: Any
    guard: Optional[Callable[..., bool]] = None
    action: Optional[Callable[..., Awaitable[None]]] = None

    def can_execute(self, **kwargs) -> bool:
        """Check if transition can execute based on guard condition."""
        if self.guard:
            return self.guard(**kwargs)
        return True

    async def execute(self, **kwargs) -> None:
        """Execute transition action callback."""
        if self.action:
            await self.action(**kwargs)
