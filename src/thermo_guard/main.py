"""
Main module for Thermo-Guard.

This module contains the main function that runs the Thermo-Guard application.
"""

import logging
import os
import sys
import time
from typing import Dict, Any

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('thermo-guard.log')
    ]
)
logger = logging.getLogger('thermo-guard')

# Import from thermo-guard package
from . import config
from .meraki_client import MerakiClient
from .vcenter_client import VCenterClient
from .cluster_operations import shutdown_cluster, power_on_cluster


def main() -> None:
    """Main function."""
    logger.info("Starting Thermo-Guard")
    
    # Validate configuration
    if not config.validate_config():
        logger.error("Invalid configuration, exiting")
        sys.exit(1)
    
    # Initialize clients
    meraki_client = MerakiClient(
        api_key=config.MERAKI_API_KEY,
        api_base_url=config.MERAKI_API_BASE_URL,
        network_id=config.MERAKI_NETWORK_ID
    )
    
    vcenter_client = VCenterClient(
        host=config.VCENTER_HOST,
        user=config.VCENTER_USER,
        password=config.VCENTER_PASSWORD
    )
    
    # Track the current state
    is_shutdown = False
    
    # Main loop
    while True:
        try:
            # Poll Meraki API
            temperature_data = meraki_client.get_temperature_alerts()
            
            if temperature_data is not None:
                # Check if there's a temperature alarm
                has_alarm = meraki_client.check_temperature_alarm(temperature_data)
                
                if has_alarm is not None:
                    # If there's a temperature alarm and the cluster is not already shut down
                    if has_alarm and not is_shutdown:
                        logger.warning("Temperature alarm detected, shutting down cluster")
                        if shutdown_cluster(vcenter_client):
                            is_shutdown = True
                    
                    # If there's no temperature alarm and the cluster is shut down
                    elif not has_alarm and is_shutdown:
                        logger.info("Temperature alarm cleared, powering on cluster")
                        if power_on_cluster(config.ILO_HOSTS):
                            is_shutdown = False
            
            # Sleep for the polling interval
            logger.debug(f"Sleeping for {config.MERAKI_POLLING_INTERVAL} seconds")
            time.sleep(config.MERAKI_POLLING_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, exiting")
            break
            
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            # Sleep for a short time to avoid tight loops in case of persistent errors
            time.sleep(10)
    
    logger.info("Thermo-Guard stopped")


if __name__ == "__main__":
    main()
