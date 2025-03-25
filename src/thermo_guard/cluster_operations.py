"""
Cluster Operations module for Thermo-Guard.

This module provides functions for shutting down and powering on the ESXi cluster.
"""

import logging
from typing import List, Dict

from .vcenter_client import VCenterClient
from .ilo_client import IloClient

logger = logging.getLogger('thermo-guard')


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
