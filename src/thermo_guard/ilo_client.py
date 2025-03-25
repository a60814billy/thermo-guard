"""
iLO Client module for Thermo-Guard.

This module provides the IloClient class for interacting with HP iLO interfaces
to power on servers.
"""

import logging

# Import redfish for iLO interaction
try:
    import redfish
except ImportError:
    logging.getLogger('thermo-guard').error("Failed to import python-ilorest-library. Make sure it's installed.")
    import sys
    sys.exit(1)

logger = logging.getLogger('thermo-guard')


class IloClient:
    """Client for interacting with iLO interfaces."""

    def __init__(self, host: str, username: str, password: str):
        self.host = host
        self.username = username
        self.password = password
        self.redfish_client = None

    def connect(self) -> bool:
        """
        Connect to the iLO interface.
        
        Returns:
            True if connection was successful, False otherwise.
        """
        try:
            logger.info(f"Connecting to iLO interface at {self.host}")
            self.redfish_client = redfish.redfish_client(
                base_url=f"https://{self.host}",
                username=self.username,
                password=self.password,
                default_prefix="/redfish/v1"
            )
            self.redfish_client.login()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to iLO interface at {self.host}: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from the iLO interface."""
        if self.redfish_client:
            try:
                self.redfish_client.logout()
                logger.info(f"Disconnected from iLO interface at {self.host}")
            except Exception as e:
                logger.error(f"Error disconnecting from iLO interface at {self.host}: {e}")
            self.redfish_client = None

    def power_on(self) -> bool:
        """
        Power on the server.
        
        Returns:
            True if power on was successful, False otherwise.
        """
        if not self.redfish_client:
            logger.error(f"Not connected to iLO interface at {self.host}")
            return False
        
        try:
            # Get the Systems collection
            systems_response = self.redfish_client.get("/Systems")
            systems_members_uri = systems_response.dict["Members"][0]["@odata.id"]
            
            # Get the System resource
            system_response = self.redfish_client.get(systems_members_uri)
            
            # Check if the system is already powered on
            if system_response.dict["PowerState"] == "On":
                logger.info(f"Server at {self.host} is already powered on")
                return True
            
            # Power on the system
            logger.info(f"Powering on server at {self.host}")
            reset_uri = system_response.dict["Actions"]["#ComputerSystem.Reset"]["target"]
            reset_response = self.redfish_client.post(reset_uri, body={"ResetType": "On"})
            
            if reset_response.status == 200:
                logger.info(f"Server at {self.host} is powering on")
                return True
            else:
                logger.error(f"Failed to power on server at {self.host}: {reset_response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error powering on server at {self.host}: {e}")
            return False
