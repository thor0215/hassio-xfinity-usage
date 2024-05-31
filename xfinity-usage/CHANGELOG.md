# Changelog

## 0.0.9

- Encypt the Xfinity password in the log file when in debug mode
- Added debug_support logging option to gather page source and screenshots when extra troubleshooting is needed.
- Version bump pip requirements:
    - playwright to 1.44.0
    - typing-extensions to 4.12.0
    - pyee to 11.1.0
    - greenlet to 3.0.3
    - tenacity to 8.3.0
    - requests to 2.32.3

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
