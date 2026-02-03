import json
import logging
import os
import boto3
from urllib import request, parse, error

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Secret name in Secrets Manager
SECRET_NAME = "myOpenWeatherAPIKey" #REPLACE WITH YOUR WEATHER API SECRET NAME
REGION = os.environ.get("AWS_REGION", "us-east-1")

# Secrets Manager client
secrets_client = boto3.client("secretsmanager", region_name=REGION)

def get_api_key():
    """Fetch OpenWeather API key from Secrets Manager (JSON secret)"""
    try:
        response = secrets_client.get_secret_value(SecretId=SECRET_NAME)
        secret_value = response.get("SecretString", "")
        secret_json = json.loads(secret_value)
        api_key = secret_json.get("OPENWEATHER_API_KEY")
        if not api_key:
            raise ValueError("API key not found in secret")
        logger.info("Successfully fetched API key from Secrets Manager")
        return api_key
    except Exception as e:
        logger.error(f"Failed to fetch API key from Secrets Manager: {e}")
        raise

def lambda_handler(event, context):
    """
    Lambda entrypoint
    Event format: { "city": "New York" }
    Returns: { "city": ..., "temperature": ..., "condition": ..., "source": ... }
    """

    logger.info(f"Received event: {json.dumps(event)}")

    city = event.get("city")
    if not city:
        return {"error": "City is required"}

    try:
        api_key = get_api_key()
        params = parse.urlencode({"q": city, "appid": api_key, "units": "imperial"})
        url = f"https://api.openweathermap.org/data/2.5/weather?{params}"

        with request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        result = {
            "city": city,
            "temperature": f"{data['main']['temp']} F",
            "condition": data["weather"][0]["description"],
            "source": "OpenWeather API"
        }

        logger.info(f"Returning weather: {result}")
        return result

    except error.HTTPError as e:
        logger.error(f"HTTP error calling OpenWeather API: {e}")
        return {"error": f"HTTP error calling OpenWeather API: {e}"}
    except error.URLError as e:
        logger.error(f"Request error: {e}")
        return {"error": f"Request error: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": f"Unexpected error: {e}"}

