# Implementation Plan: Automated ESXi Cluster Shutdown and Power-On based on Temperature Alarm

This document outlines the implementation plan for the Thermo-Guard system, which automatically shuts down an ESXi cluster when a high-temperature alarm is detected by Cisco Meraki and powers it back on when the alarm recovers.

## 1. Project Setup

* Directory structure: `thermo-guard/`
* Python version: 3.12
* Main files:
  * `main.py`: Main application logic
  * `config.py`: Configuration parameters
  * `requirements.txt`: Project dependencies
  * `Dockerfile`: For building the Docker image
  * `.gitignore`: Excludes unnecessary files from version control

## 2. Configuration (`config.py`)

The `config.py` file will define the following configuration parameters, read from environment variables:

* `MERAKI_API_KEY`: Meraki API key (string)
* `MERAKI_NETWORK_ID`: Meraki Network ID (string)
* `MERAKI_API_BASE_URL`: `https://api.meraki.com/api/v1` (string, constant)
* `MERAKI_POLLING_INTERVAL`: Polling interval in seconds (integer, default: 60)
* `TEMPERATURE_HIGH_THRESHOLD`: High-temperature threshold in Celsius (integer/float, default: 35)
* `TEMPERATURE_LOW_THRESHOLD`: Low-temperature threshold in Celsius (integer/float, default: 30)
* `VCENTER_HOST`: vCenter Server hostname/IP (string)
* `VCENTER_USER`: vCenter username (string)
* `VCENTER_PASSWORD`: vCenter password (string)
* `ILO_HOSTS`: A list of dictionaries, each containing `host`, `username`, and `password` for each ESXi host's iLO interface. Example:
  ```python
  [
      {"host": "ilo1_ip", "username": "ilo1_user", "password": "ilo1_pass"},
      {"host": "ilo2_ip", "username": "ilo2_user", "password": "ilo2_pass"},
  ]
  ```

## 3. Main Logic (`main.py`)

### 3.1 Initialization

* Load configuration from environment variables using `config.py`
* Initialize connections to vCenter (using pyvmomi) and the Meraki API
* Initialize iLO connections (using `python-ilorest-library` or a suitable alternative)

### 3.2 Main Loop

#### 3.2.1 Poll Meraki API

* Construct the API URL: `f"{config.MERAKI_API_BASE_URL}/networks/{config.MERAKI_NETWORK_ID}/sensor/alerts/current/overview/byMetric"`
* Make a GET request to the Meraki API with the Authorization header: `{"Authorization": f"Bearer {config.MERAKI_API_KEY}"}`
* Handle potential API errors (e.g., network issues, invalid API key) using `try...except` blocks and retry with exponential backoff
* Parse the JSON response
* Check if the "temperature" metric exists in `supportedMetrics`. If not, log a warning and continue to the next iteration
* Get the `counts.temperature` value

#### 3.2.2 Check Alarm Status

* If `counts.temperature` is greater than `config.TEMPERATURE_HIGH_THRESHOLD`, trigger the shutdown procedure
* If `counts.temperature` is less than `config.TEMPERATURE_LOW_THRESHOLD`, trigger the power-on procedure

#### 3.2.3 Shutdown Procedure

* Connect to vCenter using pyvmomi
* Iterate through all virtual machines in the cluster:
  * Gracefully shut down each VM using VMware Tools (if available). If that fails, force power off
* Iterate through all ESXi hosts:
  * Put the host into maintenance mode
  * Shut down the host
* Handle potential vCenter API errors

#### 3.2.4 Power-On Procedure

* Iterate through `config.ILO_HOSTS`:
  * Connect to the iLO interface of each host
  * Send the power-on command
  * Handle potential iLO communication errors

#### 3.2.5 Logging

* Log all significant events (polling, alarm status changes, vCenter actions, iLO actions, errors)

#### 3.2.6 Sleep

* Wait for `config.MERAKI_POLLING_INTERVAL` seconds before the next iteration

## 4. Dockerfile

* Use `python:3.12-slim` as the base image
* Copy the project files into the container
* Install dependencies using `pip install -r requirements.txt`
* Set the entrypoint to run `main.py`

## 5. Error Handling

* Implement robust error handling for all API interactions (Meraki, vCenter, iLO)
* Use `try...except` blocks to catch exceptions and log errors
* Implement retry mechanisms with exponential backoff for transient network errors

## 6. System Architecture

```mermaid
graph LR
    subgraph "Synology NAS (Docker Container)"
        A[Automation Program (main.py)]
        Cfg[Configuration (config.py)]
    end

    subgraph "Third-Party Monitoring System (Meraki)"
        B[Meraki API]
    end

    subgraph "vCenter Server"
        C[vCenter API]
    end

    subgraph "ESXi Cluster Hosts"
        D["ESXi Host 1 (iLO)"]
        E["ESXi Host 2 (iLO)"]
        F["ESXi Host N (iLO)"]
    end

    A -- Polling --> B
    A -- vSphere API --> C
    A -- iLO Interaction --> D
    A -- iLO Interaction --> E
    A -- iLO Interaction --> F
    A -- Reads --> Cfg

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style B fill:#ccf,stroke:#333,stroke-width:2px
    style C fill:#9cf,stroke:#333,stroke-width:2px
    style D fill:#fcc,stroke:#333,stroke-width:2px
    style E fill:#fcc,stroke:#333,stroke-width:2px
    style F fill:#fcc,stroke:#333,stroke-width:2px
    style Cfg fill:#ff9,stroke:#333,stroke-width:2px
```

## 7. Dependencies

* `pyvmomi`: For interacting with vCenter
* `requests`: For making HTTP requests to the Meraki API
* `python-ilorest-library` (or equivalent): For interacting with iLO interfaces
* Logging libraries (e.g., `logging`)
* Environment variable management (e.g., `python-dotenv`)

## 8. Deployment

* Build the Docker image using the provided Dockerfile
* Deploy the Docker container on the Synology NAS using Synology's Container Manager
* Configure environment variables for the container with all required credentials and settings
* Ensure the container has network access to the Meraki API, vCenter Server, and ESXi hosts' iLO interfaces
