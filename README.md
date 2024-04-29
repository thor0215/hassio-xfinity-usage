# Home Assistant Addon to fetch Xfinity Internet Usage Data
Fetch Xfinity Internet Service Usage Data and publish it to Home Assistant sensor

## Setup
  - This addon will not work if your Xfinity account is using MFA

  1. Add this repository to Home Assistant as a source for third-party addons. See the [Home Assistant documentation](https://www.home-assistant.io/common-tasks/os#installing-third-party-add-ons) if you have questions on how to do that.
  2. Install the Xfinity Usage addon
  3. Enter your username and password using the configuration page
  4. After starting the addon, check the log for "INFO: Usage data retrieved and processed"
  5. Now go to Developer tools -> States and search for sensor.xfinity_usage

  - Usage script runs every 15 minutes (900 seconds) by default
  - Page timeout is 45 seconds by default


