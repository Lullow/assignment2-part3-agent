from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import count


# Simple runtime-only task id generator.
# Starts at 1 and increments for each queued hub task.
_task_id_counter = count(1)


@dataclass
class QueuedHubTask:
    """
    Represents a hub-originated task waiting for local approval.

    The task is not executed automatically.
    """

    # Local id used to approve, inspect, or remove this task from the queue.
    task_id: int

    # The hub sender that created/requested the task.
    sender: str

    # Original message content from the hub.
    content: str

    # Detected intent, for example execute_task, code_request, or delegate_task.
    intent: str

    # UTC timestamp showing when the task was added to the local queue.
    created_at: str


@dataclass
class HubTaskQueue:
    """
    In-memory queue for hub tasks that require local approval.

    This queue is runtime-only and is cleared when the process stops.
    """

    # Pending tasks are kept only in memory, not written to disk.
    pending_tasks: list[QueuedHubTask] = field(default_factory=list)

    def add_task(self, sender: str, content: str, intent: str) -> QueuedHubTask:
        # Create a queued task instead of executing the hub request directly.
        task = QueuedHubTask(
            task_id=next(_task_id_counter),
            sender=sender,
            content=content,
            intent=intent,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        self.pending_tasks.append(task)
        return task

    def list_tasks(self) -> list[QueuedHubTask]:
        # Return a shallow copy so callers cannot accidentally replace the queue list.
        return list(self.pending_tasks)

    def get_task(self, task_id: int) -> QueuedHubTask | None:
        # Find a task by local id. Return None if it no longer exists.
        for task in self.pending_tasks:
            if task.task_id == task_id:
                return task

        return None

    def remove_task(self, task_id: int) -> QueuedHubTask | None:
        # Remove only after finding the task, so invalid ids are handled safely.
        task = self.get_task(task_id)

        if task is None:
            return None

        self.pending_tasks.remove(task)
        return task