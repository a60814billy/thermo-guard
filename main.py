#!/usr/bin/env python3
"""
Thermo-Guard: Automated ESXi Cluster Shutdown and Power-On based on Temperature Alarm

This script monitors temperature alarms from Cisco Meraki and automatically shuts down
an ESXi cluster when a high-temperature alarm is detected, and powers it back on when
the alarm recovers.
"""

import logging
import os
import sys
import time
import json
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import configuration
import config

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

# Import pyvmomi for vCenter interaction
try:
    from pyVim import connect
    from pyVmomi import vim
except ImportError:
    logger.error("Failed to import pyvmomi. Make sure it's installed.")
    sys.exit(1)

# Import redfish for iLO interaction
try:
    import redfish
except ImportError:
    logger.error("Failed to import python-ilorest-library. Make sure it's installed.")
    sys.exit(1)


class MerakiClient:
    """Client for interacting with the Meraki API."""

    def __init__(self, api_key: str, api_base_url: str, network_id: str):
        self.api_key = api_key
        self.api_base_url = api_base_url
        self.network_id = network_id
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
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
                    logger.warning(f"Meraki API returned status code {response.status_code}: {response.text}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error polling Meraki API: {e}")
            
            # Exponential backoff
            if attempt < max_retries - 1:
                sleep_time = retry_delay * (2 ** attempt)
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


class VCenterClient:
    """Client for interacting with vCenter."""

    def __init__(self, host: str, user: str, password: str):
        self.host = host
        self.user = user
        self.password = password
        self.service_instance = None

    def connect(self) -> bool:
        """
        Connect to vCenter.
        
        Returns:
            True if connection was successful, False otherwise.
        """
        try:
            logger.info(f"Connecting to vCenter at {self.host}")
            self.service_instance = connect.SmartConnect(
                host=self.host,
                user=self.user,
                pwd=self.password,
                disableSslCertValidation=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to vCenter: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from vCenter."""
        if self.service_instance:
            connect.Disconnect(self.service_instance)
            logger.info("Disconnected from vCenter")
            self.service_instance = None

    def get_all_vms(self) -> List[vim.VirtualMachine]:
        """
        Get all virtual machines in the vCenter inventory.
        
        Returns:
            List of VirtualMachine objects.
        """
        if not self.service_instance:
            logger.error("Not connected to vCenter")
            return []
        
        content = self.service_instance.RetrieveContent()
        container = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True
        )
        vms = container.view
        container.Destroy()
        
        logger.info(f"Found {len(vms)} virtual machines")
        return vms

    def get_all_hosts(self) -> List[vim.HostSystem]:
        """
        Get all ESXi hosts in the vCenter inventory.
        
        Returns:
            List of HostSystem objects.
        """
        if not self.service_instance:
            logger.error("Not connected to vCenter")
            return []
        
        content = self.service_instance.RetrieveContent()
        container = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.HostSystem], True
        )
        hosts = container.view
        container.Destroy()
        
        logger.info(f"Found {len(hosts)} ESXi hosts")
        return hosts

    def shutdown_vm(self, vm: vim.VirtualMachine) -> bool:
        """
        Shut down a virtual machine.
        
        Args:
            vm: The VirtualMachine object to shut down.
            
        Returns:
            True if shutdown was successful, False otherwise.
        """
        if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
            logger.info(f"VM '{vm.name}' is already powered off")
            return True
        
        try:
            logger.info(f"Shutting down VM '{vm.name}'")
            
            # Try graceful shutdown first
            if vm.guest.toolsRunningStatus == "guestToolsRunning":
                logger.info(f"Using VMware Tools to shut down VM '{vm.name}'")
                vm.ShutdownGuest()
                
                # Wait for up to 5 minutes for the VM to shut down
                for _ in range(30):
                    if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
                        logger.info(f"VM '{vm.name}' has been shut down gracefully")
                        return True
                    time.sleep(10)
                
                logger.warning(f"Graceful shutdown of VM '{vm.name}' timed out, forcing power off")
            else:
                logger.warning(f"VMware Tools not running on VM '{vm.name}', forcing power off")
            
            # Force power off if graceful shutdown failed or VMware Tools not running
            task = vm.PowerOff()
            # Wait for the task to complete
            while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
                time.sleep(1)
            
            if task.info.state == vim.TaskInfo.State.success:
                logger.info(f"VM '{vm.name}' has been powered off")
                return True
            else:
                logger.error(f"Failed to power off VM '{vm.name}': {task.info.error}")
                return False
                
        except Exception as e:
            logger.error(f"Error shutting down VM '{vm.name}': {e}")
            return False

    def enter_maintenance_mode(self, host: vim.HostSystem) -> bool:
        """
        Put an ESXi host into maintenance mode.
        
        Args:
            host: The HostSystem object to put into maintenance mode.
            
        Returns:
            True if entering maintenance mode was successful, False otherwise.
        """
        if host.runtime.inMaintenanceMode:
            logger.info(f"Host '{host.name}' is already in maintenance mode")
            return True
        
        try:
            logger.info(f"Putting host '{host.name}' into maintenance mode")
            task = host.EnterMaintenanceMode(timeout=600)
            
            # Wait for the task to complete
            while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
                time.sleep(5)
            
            if task.info.state == vim.TaskInfo.State.success:
                logger.info(f"Host '{host.name}' is now in maintenance mode")
                return True
            else:
                logger.error(f"Failed to put host '{host.name}' into maintenance mode: {task.info.error}")
                return False
                
        except Exception as e:
            logger.error(f"Error putting host '{host.name}' into maintenance mode: {e}")
            return False

    def shutdown_host(self, host: vim.HostSystem) -> bool:
        """
        Shut down an ESXi host.
        
        Args:
            host: The HostSystem object to shut down.
            
        Returns:
            True if shutdown was successful, False otherwise.
        """
        if not host.runtime.inMaintenanceMode:
            logger.error(f"Host '{host.name}' is not in maintenance mode, cannot shut down")
            return False
        
        try:
            logger.info(f"Shutting down host '{host.name}'")
            task = host.ShutdownHost_Task(force=False)
            
            # Wait for the task to complete
            while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
                time.sleep(5)
            
            if task.info.state == vim.TaskInfo.State.success:
                logger.info(f"Host '{host.name}' is shutting down")
                return True
            else:
                logger.error(f"Failed to shut down host '{host.name}': {task.info.error}")
                return False
                
        except Exception as e:
            logger.error(f"Error shutting down host '{host.name}': {e}")
            return False


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


def shutdown_cluster(vcenter_client: VCenterClient) -> bool:
    """
    Shut down the ESXi cluster.
    
    Args:
        vcenter_client: The VCenterClient to use for the shutdown.
        
    Returns:
        True if shutdown was successful, False otherwise.
    """
    logger.info("Starting cluster shutdown procedure")
    
    # Connect to vCenter
    if not vcenter_client.connect():
        logger.error("Failed to connect to vCenter, aborting shutdown")
        return False
    
    try:
        # Get all VMs
        vms = vcenter_client.get_all_vms()
        
        # Shut down all VMs
        logger.info("Shutting down all virtual machines")
        for vm in vms:
            vcenter_client.shutdown_vm(vm)
        
        # Get all hosts
        hosts = vcenter_client.get_all_hosts()
        
        # Put all hosts into maintenance mode and shut them down
        logger.info("Putting all hosts into maintenance mode and shutting them down")
        for host in hosts:
            if vcenter_client.enter_maintenance_mode(host):
                vcenter_client.shutdown_host(host)
        
        logger.info("Cluster shutdown procedure completed")
        return True
        
    except Exception as e:
        logger.error(f"Error during cluster shutdown: {e}")
        return False
        
    finally:
        # Disconnect from vCenter
        vcenter_client.disconnect()


def power_on_cluster(ilo_hosts: List[Dict[str, str]]) -> bool:
    """
    Power on the ESXi cluster.
    
    Args:
        ilo_hosts: List of dictionaries containing iLO host information.
        
    Returns:
        True if power on was successful, False otherwise.
    """
    logger.info("Starting cluster power-on procedure")
    
    success = True
    
    # Power on all hosts
    for host_info in ilo_hosts:
        ilo_client = IloClient(
            host=host_info["host"],
            username=host_info["username"],
            password=host_info["password"]
        )
        
        if ilo_client.connect():
            if not ilo_client.power_on():
                success = False
            ilo_client.disconnect()
        else:
            success = False
    
    if success:
        logger.info("Cluster power-on procedure completed successfully")
    else:
        logger.warning("Cluster power-on procedure completed with errors")
    
    return success


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
