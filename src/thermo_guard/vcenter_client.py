"""
vCenter Client module for Thermo-Guard.

This module provides the VCenterClient class for interacting with vCenter
to manage ESXi hosts and virtual machines.
"""

import logging
import time
from typing import List

# Import pyvmomi for vCenter interaction
try:
    from pyVim import connect
    from pyVmomi import vim
except ImportError:
    logging.getLogger("thermo-guard").error(
        "Failed to import pyvmomi. Make sure it's installed."
    )
    import sys

    sys.exit(1)

logger = logging.getLogger("thermo-guard")


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
                disableSslCertValidation=True,
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

                logger.warning(
                    f"Graceful shutdown of VM '{vm.name}' timed out, forcing power off"
                )
            else:
                logger.warning(
                    f"VMware Tools not running on VM '{vm.name}', forcing power off"
                )

            # Force power off if graceful shutdown failed or VMware Tools not running
            task = vm.PowerOff()
            # Wait for the task to complete
            while task.info.state not in [
                vim.TaskInfo.State.success,
                vim.TaskInfo.State.error,
            ]:
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
            while task.info.state not in [
                vim.TaskInfo.State.success,
                vim.TaskInfo.State.error,
            ]:
                time.sleep(5)

            if task.info.state == vim.TaskInfo.State.success:
                logger.info(f"Host '{host.name}' is now in maintenance mode")
                return True
            else:
                logger.error(
                    f"Failed to put host '{host.name}' into maintenance mode: {task.info.error}"
                )
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
            logger.error(
                f"Host '{host.name}' is not in maintenance mode, cannot shut down"
            )
            return False

        try:
            logger.info(f"Shutting down host '{host.name}'")
            task = host.ShutdownHost_Task(force=False)

            # Wait for the task to complete
            while task.info.state not in [
                vim.TaskInfo.State.success,
                vim.TaskInfo.State.error,
            ]:
                time.sleep(5)

            if task.info.state == vim.TaskInfo.State.success:
                logger.info(f"Host '{host.name}' is shutting down")
                return True
            else:
                logger.error(
                    f"Failed to shut down host '{host.name}': {task.info.error}"
                )
                return False

        except Exception as e:
            logger.error(f"Error shutting down host '{host.name}': {e}")
            return False
