"""
base.py — Job module contracts (documentation only; no runtime classes).

A "Scheduled" job module (under jobs/Scheduled/) must define:

    TRIGGER: dict   — APScheduler trigger kwargs, e.g.:
        {"type": "cron", "hour": 8, "minute": 0}
        {"type": "cron", "day": 1, "hour": 4, "minute": 0}
        {"type": "interval", "hours": 6}

    def run(client: PlankaClient) -> None: ...

Example:

    from planka_tools.api.client import PlankaClient

    TRIGGER = {"type": "cron", "hour": 8, "minute": 0}

    def run(client: PlankaClient) -> None:
        ...

A "Webhook" job module (under jobs/Webhook/) must define:

    EVENTS: list[str]   — Planka event names this job subscribes to, e.g. ["cardUpdate"]

    def run(event: str, payload: dict, client: PlankaClient) -> None: ...

Example:

    from planka_tools.api.client import PlankaClient

    EVENTS = ["cardUpdate"]

    def run(event: str, payload: dict, client: PlankaClient) -> None:
        ...

Modules missing any required attribute are logged and skipped by
`planka_tools.jobs.loader` — they never crash the scheduler or webhook
dispatcher.
"""
