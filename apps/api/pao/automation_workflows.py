"""Deterministic Temporal workflows.

Keep this module free of PAO configuration, database, filesystem, and network
imports. Temporal re-imports workflow modules inside its deterministic sandbox.
"""
from datetime import datetime, timedelta, timezone

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn
class PaoAutomationWorkflow:
    def __init__(self):
        self.decision: dict | None = None
        self.cancelled = False

    @workflow.signal
    def approve(self, data: dict) -> None:
        self.decision = {"decision": "approved", **data}

    @workflow.signal
    def reject(self, data: dict) -> None:
        self.decision = {"decision": "rejected", **data}

    @workflow.signal
    def request_cancel(self, data: dict) -> None:
        self.cancelled = True

    @workflow.query
    def state(self) -> dict:
        return {"decision": self.decision, "cancelled": self.cancelled}

    async def _project(self, item: dict, status: str, **extra) -> None:
        await workflow.execute_activity(
            "project_workflow",
            {"id": item["id"], "status": status, **extra},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )

    @workflow.run
    async def run(self, item: dict) -> dict:
        if item["approval_required"]:
            await self._project(item, "waiting_approval", approval_status="pending")
            try:
                await workflow.wait_condition(
                    lambda: self.decision is not None or self.cancelled,
                    timeout=timedelta(hours=item["approval_timeout_hours"]),
                )
            except TimeoutError:
                await self._project(
                    item,
                    "cancelled",
                    approval_status="rejected",
                    result={"reason": "approval_timeout"},
                )
                return {"status": "cancelled", "reason": "approval_timeout"}
            if self.cancelled or self.decision["decision"] == "rejected":
                result = {"reason": "cancelled" if self.cancelled else "rejected"}
                await self._project(
                    item,
                    "cancelled",
                    approval_status="rejected",
                    result=result,
                )
                return {"status": "cancelled", **result}
            await self._project(item, "running", approval_status="approved")
        if item.get("wait_until"):
            target = datetime.fromisoformat(item["wait_until"]).astimezone(timezone.utc)
            seconds = max(0, (target - workflow.now()).total_seconds())
            if seconds:
                await self._project(item, "waiting_timer")
                try:
                    await workflow.wait_condition(
                        lambda: self.cancelled,
                        timeout=timedelta(seconds=seconds),
                    )
                except TimeoutError:
                    pass
        if self.cancelled:
            await self._project(item, "cancelled", result={"reason": "cancelled"})
            return {"status": "cancelled"}
        result = {"kind": item["kind"], "payload": item["payload"], "completed": True}
        await self._project(item, "completed", result=result)
        return result
