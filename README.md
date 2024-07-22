# Home Assistant Addon to fetch Xfinity Internet Usage Data

Fetch Xfinity Internet Service Usage Data and publish it to a Home Assistant sensor. The Python code logic was originally based on [zachowj/xfinity-data-usage](https://github.com/zachowj/xfinity-data-usage) and uses [Playwright](https://playwright.dev/python/).

[![pypi_badge](https://img.shields.io/pypi/v/playwright.svg)](https://pypi.python.org/pypi/playwright)

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

[<img src="images/bmc-button.svg" width=125 style="margin: 5px"/>](https://www.buymeacoffee.com/thor0215)

## Setup

### This addon will not work if your Xfinity account is using MFA

1. Add this repository `https://github.com/thor0215/hassio-xfinity-usage` to Home Assistant as a source for third-party addons. See the [Home Assistant documentation](https://www.home-assistant.io/common-tasks/os#installing-third-party-add-ons) if you have questions on how to do that. You can also use the button below.

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https://github.com/thor0215/hassio-xfinity-usage/)

2. Install the Xfinity Usage addon
3. Enter your username and password using the configuration page
4. If you are using MQTT, see the [MQTT Setup](#mqtt-setup) instructions below
5. After starting the addon, check the log for "INFO: Usage data retrieved and processed"
6. Now go to Developer tools -> States and search for sensor.xfinity_usage or for MQTT setups, sensor.xfinity_internet_usage

Addon Defaults: Page Timeout is 45 seconds and the script runs every 15 minutes (900 seconds)

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

## MQTT Setup

Enable MQTT and enter the MQTT Broker information and login if necessary. Note if you are using the Moquitto MQTT addon, the startup logs will show the necessary MQTT broker info like this

```text
---
MQTT addon is active on your system!
Add the MQTT details below to the addon configuration :
MQTT user : addons
MQTT password : Ri5ahV1aipeiw0aelerooteixai5ohtoeNg6oo3mo0thi5te0phiezuge4Phoore
MQTT Hostname : core-mosquitto
MQTT Port : 1883
---
```

![Enable MQTT](./images/mqtt_enable_service.png)

Then check your MQTT Devices

![MQTT Device](./images/mqtt_device.png)

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-no-red.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-no-red.svg
[releases]: https://github.com/thor0215/hassio-xfinity-usage/releases
