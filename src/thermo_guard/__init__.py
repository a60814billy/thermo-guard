"""
Thermo-Guard: Automated ESXi Cluster Shutdown and Power-On based on Temperature Alarm

This package monitors temperature alarms from Cisco Meraki and automatically shuts down
an ESXi cluster when a high-temperature alarm is detected, and powers it back on when
the alarm recovers.
"""

from .cluster_operations import power_on_cluster, shutdown_cluster
from .config import validate_config
from .ilo_client import IloClient
from .meraki_client import MerakiClient
from .vcenter_client import VCenterClient
