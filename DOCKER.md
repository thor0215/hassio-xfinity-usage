# Docker/Kubernetes Guide

This is not well tested and any user feedback/recommendations will be greatly appreciated.

There are 2 steps needed.

First run will create the /config/.code.json file needed for Second run. The script will also output the special Xfinity login url to gather the "code"

Second run, supply the XFINITY_CODE using the "code" gathered from Step 1. Script should now hopefully be able to get a refresh token. The refresh token is saved in the /config/.token.json file.  You can supply the refresh token as an environment variable "REFRESH_TOKEN" for any additional runs. The script will use REFRESH_TOKEN if provided otherwise it will use the token provided in the /config/.token.json file.

## Install the development build as a local Home Assistant app

These steps install the published `2026.11.1` development image on Home Assistant OS. The image supports `amd64` and `aarch64`. The local app configuration points to the published image, so Home Assistant pulls it instead of building it from source.

1. Stop the regular Xfinity app while testing. Do not run both versions at the same time: they publish the same Home Assistant sensor IDs and MQTT discovery IDs.
2. Make the Home Assistant `local_apps` folder available. Install the Samba share app and open its `local_apps` share, or use Terminal & SSH and work in `/local_apps`.
3. Download the [development branch archive](https://github.com/thor0215/hassio-xfinity-usage/archive/refs/heads/development/2026.11.1.zip) and extract it on your computer.
4. Create `/local_apps/xfinity-usage-dev/` and copy the **contents** of the archive's `xfinity_usage/` folder into it. The resulting directory must contain `config.yaml` directly, for example `/local_apps/xfinity-usage-dev/config.yaml`.
5. In that copied `config.yaml`, change only the app name and slug so it can coexist with the regular repository entry:

   ```yaml
   name: "Xfinity Internet and Mobile Usage (Dev)"
   slug: "xfinity-usage-dev"
   ```

   Leave `version: "2026.11.1"` and `image: "ghcr.io/thor0215/hassio-xfinity-usage"` unchanged. Home Assistant uses the version as the image tag, pulling `ghcr.io/thor0215/hassio-xfinity-usage:2026.11.1`.
6. In Home Assistant, open **Settings > Apps**, open the app store menu, and select **Check for updates**. Refresh the page if needed; the app should appear under **Local apps**. Install it.
7. Configure the app with your own Xfinity refresh token, or follow the [Xfinity login setup](./README.md#installation). Because this is a separate app slug, configure its token and MQTT options separately. Save the configuration, then start the app and check its logs.

The GHCR image must be readable by your Home Assistant host. If Home Assistant reports an image-pull authorization error, the package needs public read access or authenticated registry access. Do not put registry credentials or Xfinity tokens in the shared app files.

When testing is finished, stop and uninstall **Xfinity Internet and Mobile Usage (Dev)**, remove `/local_apps/xfinity-usage-dev/`, and start the regular Xfinity app again. Keep the two versions stopped from running simultaneously.

## Docker Compose Example[^1]

```yaml
services:
  xfinity:
    image: ghcr.io/thor0215/hassio-xfinity-usage-amd64:latest
    container_name: xfinity
    entrypoint: /bin/sh -c "python3 -Wignore -m xfinity_usage"
    restart: unless-stopped
    environment:
      TZ: America/Chicago
      BYPASS: 1
      MQTT_SERVICE: true
      MQTT_HOST: <mqtt ip/dns>
      MQTT_PORT: 1883
      MQTT_USERNAME: <user>
      MQTT_PASSWORD: <password>
      MQTT_RAW_USAGE: true
      INTERNET_USAGE_ENABLED: "true"
      MOBILE_USAGE_ENABLED: "true"
      MOBILE_DIAGNOSTICS_ENABLED: "false"
      LOG_LEVEL: info
      POLLING_RATE: 3600
    volumes:
      - /some/local/path/config:/config
    shm_size: 1gb
```

## Kubernetes Example[^2]

This example uses Kubernetes Cronjob subsystem to control the polling rate. BYPASS is set to 0

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: xfinity_usage
  namespace: tools
spec:
  schedule: "0/30 * * * *"
  concurrencyPolicy: Forbid
  failedJobsHistoryLimit: 3
  successfulJobsHistoryLimit: 1
  startingDeadlineSeconds: 360 # 6 min
  jobTemplate:
    spec:
      backoffLimit: 0 # Don't retry.
      template:
        spec:
          initContainers:
            - name: create-log
              image: busybox
              command: ["touch", "/config/xfinity.log"] # Create the log file.
              volumeMounts:
                - mountPath: /config
                  name: config
          containers:
            - name: xfinity-usage
              image: ghcr.io/thor0215/hassio-xfinity-usage-aarch64:0.0.12.7.2.2@sha256:897360c2f9e8e85d040f6da18ae11c1b524f80dec5c40b703e717df69272bba9
              imagePullPolicy: IfNotPresent
              command: ["/bin/bash"]
              args: ["-c", "python3 -Wignore -m xfinity_usage || true"] # Always return true while oneshot mode is not supported.
              resources:
                limits:
                  memory: 4Gi
                  cpu: 1000m
                requests:
                  memory: 2Gi
                  cpu: 200m
              env:
                - name: TZ
                  value: America/Chicago
                - name: BYPASS
                  value: "0"
                - name: PAGE_TIMEOUT
                  value: "60"
                - name: LOGLEVEL
                  value: "info"
                - name: MQTT_SERVICE
                  value: "true"
                - name: MQTT_USERNAME
                  valueFrom:
                    secretKeyRef:
                      key: MQTT_USERNAME
                      name: xfinity-usage-secret
                - name: MQTT_PASSWORD
                  valueFrom:
                    secretKeyRef:
                      key: MQTT_PASSWORD
                      name: xfinity-usage-secret
                - name: MQTT_HOST
                  value: "mqtt.example.com"
                - name: MQTT_PORT
                  value: "443" # Or 1883 for unencrypted mqtt.
                - name: INTERNET_USAGE_ENABLED
                  value: "true"
                - name: MOBILE_USAGE_ENABLED
                  value: "true"
                - name: MOBILE_DIAGNOSTICS_ENABLED
                  value: "false"
              volumeMounts:
                - mountPath: /config
                  name: config
          volumes:
            - emptyDir:
                medium: Memory
                sizeLimit: 1Gi
              name: config
          restartPolicy: Never
          securityContext:
            runAsNonRoot: false
```
## Environment Variables

```bash
# Level of logging
# info or debug
# info is default
LOG_LEVEL="info"

# Bypass BASHIO config in run.sh
# BYPASS=0 is default behavior for Home Assistant support
BYPASS=0

# Controls how often the script will run in seconds
# Default is 3600 (60 minutes)
#
# POLLING_RATE=0 will cause script to run once and exit
POLLING_RATE=3600

# Will delete all saved token json files
# in the /config volume
# Default is false
CLEAR_TOKEN="false"

# Run script once to get log in url
# place code value in this variable
# Script can now get refresh_token
XFINITY_CODE="<32 character string>"

# Optional variable for refresh_token
# Refresh token is stored in /config volume
# /config/.token.json
REFRESH_TOKEN="<random character string>"

# HTTP Request timeout value
# Default is 60 seconds
PAGE_TIMEOUT=60

# ******** MQTT Variables ********
# Enable MQTT
MQTT_SERVICE="false"

# MQTT Server Hostname
MQTT_HOST="<mqtt server ip/dns>"

# MQTT Server Port Number
MQTT_PORT=1883

# MQTT Username
MQTT_USERNAME="<username>"

# MQTT Password
MQTT_PASSWORD="<password>"

# Enable publishing Raw Usage JSON to MQTT
MQTT_RAW_USAGE="false"

# Usage and diagnostics options for standalone or Kubernetes deployments.
# Home Assistant users should set these in the app configuration instead.
INTERNET_USAGE_ENABLED="true"
MOBILE_USAGE_ENABLED="true"
MOBILE_DIAGNOSTICS_ENABLED="false"

# ******** Optional Variables ********
# https://developers.home-assistant.io/docs/supervisor/development/#supervisor-api-access
# Remote API proxy allows for API access outside of Home Assistant
# Home Assistant Supervisor API
BASHIO_SUPERVISOR_API="http://homeassistant_ip_dns:port"

# Home Assistant Supervisor Token
BASHIO_SUPERVISOR_TOKEN=

# Placeholder for OAuth Client Secret
# This should normally not be needed
CLIENT_SECRET

```

[^1]: Based on an example from [@zachowj](https://github.com/zachowj)
[^2]: Based on an example from [@csobrinho](https://github.com/csobrinho)