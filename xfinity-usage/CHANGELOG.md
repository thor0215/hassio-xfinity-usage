# Changelog

## 0.0.12.8.1

- If POLLING_RATE is zero and exit with success code instead of detecting HA Addon

## 0.0.12.8

- Switched User Agent to Android. Set Android (10-13) and Firefox (120-124) versions randomly.
    - Setting Firefox user agent to use a lower version causes less login/Akamai errors
- No longer using browser persistent storage. I didn't really help anything
- Added exit code enum class to better track exit codes
- Changed LOGLEVEL Addon variable to LOG_LEVEL so it links to bashio's log level variable
- Improve the usage of the addon by non-hassio consumers (docker and kubernetes) [#36](https://github.com/thor0215/hassio-xfinity-usage/issues/36)
    - run.sh will only execute bashio calls if it detects bashio
    - xfinity_usage_addon.py script will only do polling if bashio was detected

- Dependency updates
    - Update Debian base image to v12.7
    - Bump playwright from 1.46.0 to 1.47.0 in /xfinity-usage
    - Bump pyee from 11.1.0 to 12.0.0 in /xfinity-usage
    - Removed greenlet requirement, Playwright will install the version it supports. This was causing Dependabot to create unnecessary Pull Requests

## 0.0.12.7.2.2

- Second attempt to Fix MQTT Auto discovery issue when MQTT device has null values. Issue [#22](https://github.com/thor0215/hassio-xfinity-usage/issues/22)

## 0.0.12.7.2.1

- Exclude profile folder from backups

## 0.0.12.7.2

- Script logs an error if the MQTT server is unreachable
- Fixed Enable MQTT configuration option
- Update debian_12/curl to v7.88.1-10+deb12u7
- Now providing pre-built containers. Issue [#23](https://github.com/thor0215/hassio-xfinity-usage/issues/23)

## 0.0.12.7.1

- Fixes MQTT Auto discovery issue when MQTT device has null values. Issue [#22](https://github.com/thor0215/hassio-xfinity-usage/issues/22)
- Fixes MQTT does not support TLS. Issue [#25](https://github.com/thor0215/hassio-xfinity-usage/issues/25)

## 0.0.12.7

- Minor code cleanup
- When configured for Debug logging, a log file is now created in the addons_config folder
- Two Step verification and Akamai Access Denied detection
- Browser persistent storage is now used
- The script removes persistent storage and xfinity.log from the addon_config folder during startup
- The Firefox user agent and version are not randomized

## 0.0.12.6

- Switched to Debian 12 docker
- Added page init script to help with bot detection
- The script now blocks Xfinity domains base on EasyPrivacy filter list
- Default Page Timeout is now 60 seconds 
- Bumped Python modules
    - typing-extensions to v4.12.2
    - tenacity to v9.0.0
    - PyJWT to v2.9.0
    - playwright to v1.46.0 (includes Firefox 128.0)


## 0.0.12

- Updated Docker file
    - curl to v7.81.0-1ubuntu1.17
    - s6-overlay to v3.2.0.0
- Adjusted Playwright to use Desktop Firefox device emulation

## 0.0.11.1

- Resolved issue with Xfinity customers who have the unlimited plan and/or are using the xFi Gateway

## 0.0.11.0.4

- Working on fixing issue with Unlimited Data Plan and Xfinity Wifi modem

## 0.0.11

- Added MQTT Support

## 0.0.10.1

- Fix stable branch branding

## 0.0.10

- Removed while loop and added an assertion if the Usage data table loads but the data was not received
- Updated Docker file to no longer install software-properties-common and instead only install necessary packages for Playwright and Firefox
- Now using expect as recommended by Playwright API documentation instead of networkidle. This allows the while loop to exit once the raw plan data and usage data is received. Then the data is processed outside the while loop and pushed to the Home Assistant sensor
- Login logic and usage data gathering it now based on https://www.xfinity.com/learn/internet-service/auth page instead of https://customer.xfinity.com/#/devices#usage
- Added a lot more page checks to make sure page is properly loaded
- Session data is now based on the OAuth JWT token
- Added PyJWT library to Docker file to allow for JWT token processing
- Encrypt the Xfinity password in the log file when in debug mode
- Added debug_support logging option to gather page source and screenshots when extra troubleshooting is needed.
- Version bump pip requirements:
    - playwright to 1.44.0
    - typing-extensions to 4.12.0
    - pyee to 11.1.0
    - greenlet to 3.0.3
    - tenacity to 8.3.0
    - requests to 2.32.3
- Changes fix issues [#9](https://github.com/thor0215/hassio-xfinity-usage/issues/9) and [#8](https://github.com/thor0215/hassio-xfinity-usage/issues/8)

## 0.0.8

- Added blueprint to help users maintain sensor data between Home Assistant Restarts

## 0.0.7

- Added timestamp to logging output
- Addon will write sensor data to backup file it will use to restore the sensor upon startup.
- Adding documentation regarding how the sensor works if the addon isn't running.

## 0.0.6

- Added retry logic to prevent infinite page reloading when usage data is missing. [#2](https://github.com/thor0215/hassio-xfinity-usage/issues/2)

## 0.0.5

- Playwright sometimes has an uncaught exception in the node.js layer and script will not crash, but stops processing. Added logic to restart Playwright every 12 hrs

## 0.0.4

- Reformatted log output
- Added comments in code to better explain what's happening
- Added English translation for configuration options

## 0.0.3

- Updated Xfinity logo

## 0.0.2

- Adjusted logic so that the sensor will only be updated when the session is active and the usage data is populated

## 0.0.1

- Initial release
