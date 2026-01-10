import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")

    city = event.get("city", "Unknown City")

    return {
        "city": city,
        "temperature": "72 F",
        "condition": "Sunny",
        "source": "Lambda mock weather service"
    }
