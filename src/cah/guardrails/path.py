"""Path confinement guardrail for file actions."""

from pathlib import Path

from cah.models import Action, GuardrailDecision

FILE_ACTION_TYPES = frozenset({"read_file", "write_file"})


class PathGuardrail:
    """Ensure file actions stay inside the workspace directory."""

    def check(self, action: Action, workspace: Path) -> GuardrailDecision:
        if action.type not in FILE_ACTION_TYPES:
            return GuardrailDecision(verdict="SAFE", action_id=action.id)

        raw_path = action.params.get("path")
        if workspace is None or not raw_path:
            return GuardrailDecision(
                verdict="BLOCKED",
                reason="Cannot confine file action without workspace and path",
                risk_level="medium",
                action_id=action.id,
            )

        workspace_root = Path(workspace).resolve()
        target = (workspace_root / str(raw_path)).resolve()
        if target == workspace_root or workspace_root in target.parents:
            return GuardrailDecision(
                verdict="SAFE",
                reason="Path is inside workspace",
                action_id=action.id,
            )
        return GuardrailDecision(
            verdict="BLOCKED",
            reason=f"Path escapes workspace: {raw_path!r}",
            risk_level="high",
            action_id=action.id,
        )
