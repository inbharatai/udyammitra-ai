"""Alternate-data connector Lambda stub (Problem Statement 3 ingestion).

Triggered by EventBridge (daily GST pull) via SQS, or by AA consent webhooks.
This stub logs the trigger and returns. To run the real connectors, bundle
the app.connectors package into the Lambda (DockerImageFunction or a layer)
and wire GSP/ASP + Sahamati AA credentials from the CONNECTOR_SECRET_ARN
secret. Do not fake live pulls.
"""
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

QUEUE_URL = os.environ.get("QUEUE_URL", "")
CONNECTOR_SECRET_ARN = os.environ.get("CONNECTOR_SECRET_ARN", "")


def handler(event, context):  # noqa: ANN001
    logger.info("ingestion trigger received: %s", json.dumps(event)[:500])
    logger.info("QUEUE_URL set: %s", bool(QUEUE_URL))
    logger.info("CONNECTOR_SECRET_ARN set: %s", bool(CONNECTOR_SECRET_ARN))

    # TODO when wiring: for each SQS record, parse msme_id + source, call the
    # relevant app.connectors.<source> connector, persist raw to S3, structured
    # to Aurora, then emit a re-score event.
    return {"status": "spec_ready", "live": False, "processed": 0}