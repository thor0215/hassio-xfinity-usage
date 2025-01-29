# Home Assistant Addon to fetch Xfinity Internet Usage Data

Fetch Xfinity Internet Service Usage Data and publish it to a Home Assistant sensor.  
Thank you [@csobrinho](https://github.com/csobrinho) for your assistance in analyzing the Android Xfinity App API. And a shout out to [@Shapes0](https://github.com/Shapes0) for their insight as well.

![GitHub Release](https://img.shields.io/github/v/release/thor0215/hassio-xfinity-usage?color=blue)


![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

[<img src="https://raw.githubusercontent.com/thor0215/hassio-xfinity-usage/master/images/bmc-button.svg" width=125 style="margin: 5px"/>](https://www.buymeacoffee.com/thor0215)

## Setup

1. Add this repository `https://github.com/thor0215/hassio-xfinity-usage` to Home Assistant as a source for third-party addons. See the [Home Assistant documentation](https://www.home-assistant.io/common-tasks/os#installing-third-party-add-ons) if you have questions on how to do that. You can also use the button below.

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https://github.com/thor0215/hassio-xfinity-usage/)

## Installation

1. Install the Xfinity Usage addon

2. Run addon once, then go to Log and copy the URL shown.
3. Open a new tab in your browser.
4. Right click on the empty browser page and go to Inspect.
5. In the new DevTools window, go to Network.
6. Paste the URL into the blank browser page and log into your Xfinity account
7. If you are prompted to open an application after login, cancel the prompt.
8. Go back to the DevTools, and in the Filter type 'code?'

![Code Screenshot 1](https://raw.githubusercontent.com/thor0215/hassio-xfinity-usage/master/images/code_screenshot_1.png)

9. Click on the highlighted xerxessecure.com url.

10. Scroll to the Response Headers and find the 'Location' header
11. Copy the 'code' value. In the example below the code value is 251774815a2140a5abf64fa740dabf0c

![Code Screenshot 2](https://raw.githubusercontent.com/thor0215/hassio-xfinity-usage/master/images/code_screenshot_2.png)

12. Now go back to the Addon Configuration and paste that code into the Xfinity Code option. \
**Sometimes the Configuration page does not update the changes pushed by the script. Simply go to the list of Addons and then back into this Addons and the Configuration page should be refreshed.**

13. Now Start the Addon and check the logs.
14. If you are using MQTT, see the [MQTT Setup](https://github.com/thor0215/hassio-xfinity-usage/blob/main/MQTT.md) instructions below. If MQTT is enabled the addon will no longer update the default sensor.
15. After starting the addon, check the log for "INFO: Usage data retrieved and processed"
16. Now go to Developer tools -> States and search for sensor.xfinity_usage or for MQTT setups, sensor.xfinity_internet_usage

Addon Defaults: Page Timeout is 60 seconds and the script runs every 60 minutes (3600 seconds)

### [Docker/Kubernetes Setup](https://github.com/thor0215/hassio-xfinity-usage/blob/main/DOCKER.md)

### ***Known limitation for default sensor. This does not apply to MQTT setups.***

There is a known limitation that the sensor will be unavailable if you restart Home Assistant. This is caused by the way Home Assistant handles sensors which are not backed up by an entity, but instead come from an add-on or AppDaemon. You can easily fix that with the following blueprint:

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https://github.com/thor0215/hassio-xfinity-usage/blob/main/blueprints/restore_xfinity_internet_usage_sensor.yaml)

Or use this automation directly:

```yaml
  alias: Restore Xfinity Internet Usage sensor on startup
  description: Restore Xfinity Internet Usage sensor on startup
  trigger:
    - platform: homeassistant
      event: start
  condition: []
  action:
    - service: hassio.addon_restart
      metadata: {}
      data:
        addon: 989f231b_xfinity-usage
  mode: single
```

## Example sensor.xfinity_usage:

```
state: 554
policy_name: 1.2 Terabyte Data Plan
start_date: 04/01/2024
end_date: 04/30/2024
home_usage: 554
wifi_usage: 0
total_usage: 554
allowable_usage: 1229
unit_of_measure: GB
display_usage: true
devices:
- id: 44:A5:XX:XX:XX:XX
  usage: 559
  policyName: XI Superfast

additional_blocks_used: 0
additional_cost_per_block: 10
additional_units_per_block: 50
additional_block_size: 50
additional_included: 0
additional_used: 0
additional_percent_used: 0
additional_remaining: 0
billable_overage: 0
overage_charges: 0
overage_used: 0
current_credit_amount: 0
max_credit_amount: 0
maximum_overage_charge: 100
policy: limited
courtesy_used: 0
courtesy_remaining: 1
courtesy_allowed: 1
courtesy_months: 03/2023
in_paid_overage: false
remaining_usage: 675
friendly_name: Xfinity Usage
unit_of_measurement: GB
device_class: data_size
state_class: measurement
icon: mdi:wan
internet_download_speeds_Mbps: 800
internet_upload_speeds_Mbps: 20
```

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-no-red.svg
[armv7-shield]: https://img.shields.io/badge/armv7-no-red.svg
[i386-shield]: https://img.shields.io/badge/i386-no-red.svg
[releases-shield]: https://img.shields.io/github/release/hassio-addons/hassio-xfinity-usage.svg
[releases]: https://github.com/thor0215/hassio-xfinity-usage/releases
