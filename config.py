import os
from typing import List, Dict, Any

# Meraki API configuration
MERAKI_API_KEY = os.environ.get("MERAKI_API_KEY", "")
MERAKI_NETWORK_ID = os.environ.get("MERAKI_NETWORK_ID", "")
MERAKI_API_BASE_URL = "https://api.meraki.com/api/v1"
MERAKI_POLLING_INTERVAL = int(os.environ.get("MERAKI_POLLING_INTERVAL", "60"))

# Temperature thresholds
TEMPERATURE_HIGH_THRESHOLD = float(os.environ.get("TEMPERATURE_HIGH_THRESHOLD", "35"))
TEMPERATURE_LOW_THRESHOLD = float(os.environ.get("TEMPERATURE_LOW_THRESHOLD", "30"))

# vCenter configuration
VCENTER_HOST = os.environ.get("VCENTER_HOST", "")
VCENTER_USER = os.environ.get("VCENTER_USER", "")
VCENTER_PASSWORD = os.environ.get("VCENTER_PASSWORD", "")

# iLO hosts configuration
# Expected format in environment variable:
# ILO_HOSTS='[{"host":"ilo1_ip","username":"ilo1_user","password":"ilo1_pass"},{"host":"ilo2_ip","username":"ilo2_user","password":"ilo2_pass"}]'
ILO_HOSTS: List[Dict[str, str]] = []

ilo_hosts_env = os.environ.get("ILO_HOSTS", "[]")
try:
    import json
    ILO_HOSTS = json.loads(ilo_hosts_env)
except json.JSONDecodeError:
    print("Error: ILO_HOSTS environment variable is not valid JSON")

# Validate required configuration
def validate_config() -> bool:
    """Validate that all required configuration parameters are set."""
    if not MERAKI_API_KEY:
        print("Error: MERAKI_API_KEY environment variable is not set")
        return False
    if not MERAKI_NETWORK_ID:
        print("Error: MERAKI_NETWORK_ID environment variable is not set")
        return False
    if not VCENTER_HOST:
        print("Error: VCENTER_HOST environment variable is not set")
        return False
    if not VCENTER_USER:
        print("Error: VCENTER_USER environment variable is not set")
        return False
    if not VCENTER_PASSWORD:
        print("Error: VCENTER_PASSWORD environment variable is not set")
        return False
    if not ILO_HOSTS:
        print("Error: ILO_HOSTS environment variable is not set or is empty")
        return False
    
    for host in ILO_HOSTS:
        if not all(key in host for key in ["host", "username", "password"]):
            print(f"Error: iLO host configuration is missing required fields: {host}")
            return False
    
    return True
