"""Thin indirection between API routes and Celery so tests can swap in a
synchronous implementation without needing a running worker/broker."""

import uuid


def dispatch_document_processing(document_id: uuid.UUID) -> None:
    from app.workers.tasks import process_document_task

    process_document_task.delay(str(document_id))


def dispatch_site_processing(site_id: uuid.UUID) -> None:
    from app.workers.tasks import process_scraped_site_task

    process_scraped_site_task.delay(str(site_id))
