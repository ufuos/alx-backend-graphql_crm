# crm/celery.py
import os
from celery import Celery
from django.conf import settings

# set default Django settings module for 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crm.settings")

app = Celery("crm")

# read config from Django settings, CELERY_ prefixed keys
app.config_from_object("django.conf:settings", namespace="CELERY")

# autodiscover tasks in installed apps (looks for tasks.py)
app.autodiscover_tasks()

# optional: prefer JSON serialization
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.TIME_ZONE if hasattr(settings, "TIME_ZONE") else "UTC",
    enable_utc=True,
)
