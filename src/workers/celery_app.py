"""
Celery application for TalkGPT workers.
"""

import os
from celery import Celery


def _broker_url() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


celery_app = Celery(
    "talkgpt",
    broker=_broker_url(),
    backend=os.getenv("REDIS_BACKEND", _broker_url()),
)

# Reasonable defaults
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    worker_max_tasks_per_child=25,
    worker_prefetch_multiplier=1,
)


