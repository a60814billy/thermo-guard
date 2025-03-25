#!/usr/bin/env python3
"""
Thermo-Guard: Automated ESXi Cluster Shutdown and Power-On based on Temperature Alarm

This script monitors temperature alarms from Cisco Meraki and automatically shuts down
an ESXi cluster when a high-temperature alarm is detected, and powers it back on when
the alarm recovers.
"""

# Add src directory to path if needed
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

# Import the main function from the thermo-guard package
try:
    from thermo_guard.main import main
except ImportError:
    print(
        "Error: Could not import from thermo-guard package. Make sure it's installed."
    )
    sys.exit(1)

if __name__ == "__main__":
    main()
