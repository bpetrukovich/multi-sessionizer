"""Domain ``run`` capability (FR-012, research R6).

The domain defines the executor contract and orchestrates plan -> execute.
The real executor lives in infrastructure; tests inject a fake.
"""

from __future__ import annotations

from typing import Protocol

from .models import CommandPlan, RuntimeSnapshot, Selection
from .plan import plan


class CommandExecutor(Protocol):
    def execute(self, cmds: CommandPlan) -> None: ...


def run(selection: Selection, snapshot: RuntimeSnapshot, executor: CommandExecutor) -> None:
    plan_ = plan(selection, snapshot)
    executor.execute(plan_)
