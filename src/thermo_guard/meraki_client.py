"""
Meraki Client module for Thermo-Guard.

This module provides the MerakiClient class for interacting with the Meraki API
to monitor temperature alerts.
"""

import logging
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger("thermo-guard")


class MerakiClient:
    """Client for interacting with the Meraki API."""

    def __init__(self, api_key: str, api_base_url: str, network_id: str):
        self.api_key = api_key
        self.api_base_url = api_base_url
        self.network_id = network_id
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def get_temperature_alerts(self) -> Optional[Dict[str, Any]]:
        """
        Poll the Meraki API for temperature alerts.

        Returns:
            Dict containing the temperature alert data, or None if an error occurred.
        """
        url = f"{self.api_base_url}/networks/{self.network_id}/sensor/alerts/current/overview/byMetric"

        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                logger.debug(f"Polling Meraki API: {url}")
                response = requests.get(url, headers=self.headers, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"Meraki API response: {data}")
                    return data
                else:
                    logger.warning(
                        f"Meraki API returned status code {response.status_code}: {response.text}"
                    )

            except requests.exceptions.RequestException as e:
                logger.error(f"Error polling Meraki API: {e}")

            # Exponential backoff
            if attempt < max_retries - 1:
                sleep_time = retry_delay * (2**attempt)
                logger.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)

        return None

    def check_temperature_alarm(self, data: Dict[str, Any]) -> Optional[bool]:
        """
        Check if there's a temperature alarm in the Meraki API response.

        Args:
            data: The JSON response from the Meraki API.

        Returns:
            True if there's a temperature alarm, False if not, None if the data doesn't contain temperature metrics.
        """
        if not data or "supportedMetrics" not in data:
            logger.warning("Invalid data format from Meraki API")
            return None

        # Check if temperature metric is supported
        if "temperature" not in data["supportedMetrics"]:
            logger.warning("Temperature metric not supported by this network")
            return None

        # Check if there are temperature alerts
        if "counts" in data and "temperature" in data["counts"]:
            temperature_count = data["counts"]["temperature"]
            logger.info(f"Temperature alert count: {temperature_count}")
            return temperature_count > 0

        logger.warning("Temperature count not found in API response")
        return None
