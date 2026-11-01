
from celery import Celery

celery_app = Celery(
    "docmind",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
    include=["app.tasks.document_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)
