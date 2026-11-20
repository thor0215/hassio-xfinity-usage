# Changelog

## 2026.11.2

- Add an opt-in local Internet and Mobile diagnostics export with rounded usage amounts and identifying fields removed.
- Support environment-variable controls for Internet, Mobile, and diagnostics options in standalone and Kubernetes deployments.

## 2026.11.1

- Add independent, default-enabled options to skip Xfinity Internet or Mobile service and usage checks.
- Add Xfinity Mobile service detection and usage sensors for the account total and individual lines, including plan, cycle, and line details; normalize usage to GB and use stable opaque line identifiers.
- Require active Mobile lines before reporting Mobile service, avoiding false detections for accounts with no subscribed lines.
- Publish Mobile sensors through Home Assistant and MQTT auto-discovery, and restore Home Assistant Mobile sensor state after restart.
- Prefer GraphQL for Internet service, plan, usage, and modem/router details; use the My Account REST API only when GraphQL is unavailable or returns incomplete data.
- Include Internet plan name and normalized download/upload speeds, use returned modem/router details for MQTT, and continue publishing usage when gateway details are unavailable.
- Bound GraphQL usage retries and handle missing, malformed, or unsupported usage and plan values without preventing REST fallback.
- Update GraphQL client headers to the Xfinity app profile for Google Pixel 11 Pro, Android 16, and app version 6.14.0.
- Stop logging raw OAuth tokens and customer identifiers.
- Update add-on branding and documentation for Internet and Mobile usage.

## 2026.11.0

- Removed the `hassio_api` and `hassio_role` permissions.
- Dependency updates:
  - Bump `paho-mqtt` from 2.1.0 to 2.2.0 in `/xfinity_usage` ([PR #200](https://github.com/thor0215/hassio-xfinity-usage/pull/200)).
  - Bump `hassio-addons/debian-base` from 9.5.0 to 9.5.2 in `/xfinity_usage` ([PR #198](https://github.com/thor0215/hassio-xfinity-usage/pull/198)).

## 2026.10.5

- Additional change to bring building up to current Home Assistant app standards.

## 2026.10.4

- Changed the base image to `debian-base` to keep it in sync with Home Assistant Community Apps Debian base images.

## 2026.10.3

- Updated the container package to the correct tag.
- Updated the image URL.
- Dependency updates:
  - Update the Debian base image to v13.7-slim.
  - Bump `requests` from 2.33.1 to 2.34.2.
  - Bump `cryptography` from 46.0.7 to 50.0.2.
  - Bump `pyjwt` from 2.12.1 to 2.15.1.
  - Bump `colorlog` from 6.10.1 to 6.12.0.
  - Bump `tenacity` from 9.1.4 to 9.2.1.

## 2026.04.1

- Dependency updates:
  - Update the Debian base image to v13.4-slim.
  - Update `debian_13/tzdata` to v2026.
  - Bump `requests` from 2.32.5 to 2.33.1.
  - Bump `cryptography` from 46.0.5 to 46.0.7.
  - Bump `pyjwt` from 2.11.0 to 2.12.1.

## 2026.02.1

- Add XFINITY_CODE validation ([#123](https://github.com/thor0215/hassio-xfinity-usage/issues/123)).
- Fix an issue that prevented current-month data from being retrieved ([#122](https://github.com/thor0215/hassio-xfinity-usage/issues/122)).
- Fix an issue where no data was retrieved ([#113](https://github.com/thor0215/hassio-xfinity-usage/issues/113)).
- Fix `KeyError: 'displayUsage'`.
- Dependency updates:
  - Update the Debian base image to v13.3-slim.
  - Update Bashio to v0.17.5.
  - Bump `cryptography` from 45.0.5 to 46.0.7.
  - Bump `tenacity` from 9.1.2 to 9.1.4.
  - Bump `pyjwt` from 2.10.1 to 2.11.0.
  - Bump `colorlog` from 6.9.0 to 6.10.1.
  - Bump `requests` from 2.32.4 to 2.32.5.

## 0.1.5.5

- Display a message if Internet Usage is disabled on the account ([#100](https://github.com/thor0215/hassio-xfinity-usage/issues/100)).
- Dependency updates:
  - Update the Debian base image to 12.11-slim.
  - Update Bashio to v0.17.0.
  - Update `cryptography` to v45.0.5.
  - Update `requests` to v2.32.4.

## 0.1.5.4

- First attempt to fix the issue where the add-on stops when internet is unavailable ([#86](https://github.com/thor0215/hassio-xfinity-usage/issues/86)).
- Handle unlimited-plan policies when no usage is returned ([#90](https://github.com/thor0215/hassio-xfinity-usage/issues/90)).
- Refresh the token correctly when running with `BYPASS=1` ([#93](https://github.com/thor0215/hassio-xfinity-usage/issues/93)).
- Dependency updates:
  - Update `debian_12/curl` to 7.88.1-10+deb12u12.
  - Update `debian_12/tzdata` to v2025b-0+deb12u1.

## 0.1.5.3

- Fix an issue that caused the add-on to stop unexpectedly ([#78](https://github.com/thor0215/hassio-xfinity-usage/issues/78)).
- Handle bad request responses in the OAuth code flow ([#82](https://github.com/thor0215/hassio-xfinity-usage/issues/82)).
- Handle random errors more gracefully.
- Dependency update: update `cryptography` to v44.0.2.

## 0.1.5.1

- Obfuscate data in log output.
- Set download and upload speeds to -1 when plan data is not returned ([#70](https://github.com/thor0215/hassio-xfinity-usage/issues/70)).
- Update the default `POLLING_RATE` from 300 to 3600 seconds.
- Add a `tenacity` retry for `ConnectionError`.

## 0.1.5

- Retrieve data from the SelfHelp API, with a fallback to GraphQL.
- Fix missing attributes ([#69](https://github.com/thor0215/hassio-xfinity-usage/issues/69)).

## 0.1.4

**Breaking change:** The add-on no longer accepts a username and password. See the updated README for setup instructions.

- Fix 1.3 merge bugs.
- Dependency updates:
  - Update the Debian base image to v12.9.
  - Remove Playwright.

## 0.1.3

- Migrate to the Mobile App Token API.
- Remove StealthConfig.

## 0.1.2.2

- Run the script in headed mode using `xvfb-run`.

## 0.1.2.1

- Update StealthConfig to the recommended settings.

## 0.1.2

- Use `playwright-stealth` to mask the headless browser signature ([PR #59](https://github.com/thor0215/hassio-xfinity-usage/pull/59)).
- Dependency updates:
  - Update Playwright to v1.49.1.
  - Update `playwright-stealth` to v1.0.6.

## 0.1.1

- Update `AUTH_URL` to reflect changes on Xfinity's website.
- Add the ability to delete the browser profile on startup using an environment variable or configuration option.
- Log out of Xfinity on startup to prevent issues from lingering session data.
- Dependency updates:
  - Update Playwright to v1.49.
  - Update PyJWT to v2.10.1.
  - Update `colorlog` to v6.9.0.

## 0.1.0

- Move the polling function from the Python script into `run.sh`.
- Limit script runtime to the polling rate.
- Add colors to log output.
- Dependency update: update `colorlog` to v6.8.2.

## 0.0.12.8.2

- Fix startup errors and warnings in the Xfinity Usage add-on ([#46](https://github.com/thor0215/hassio-xfinity-usage/issues/46)).
- Add the `BYPASS` environment variable to improve support for non-Home Assistant users ([#36](https://github.com/thor0215/hassio-xfinity-usage/issues/36)).

## 0.0.12.8.1

- Exit successfully when `POLLING_RATE` is zero instead of detecting a Home Assistant add-on ([#42](https://github.com/thor0215/hassio-xfinity-usage/issues/42)).
- Add an option to publish raw usage data to the MQTT Xfinity topic ([#41](https://github.com/thor0215/hassio-xfinity-usage/issues/41)).
- Fix the `DEBUG_SUPPORT` option, which was broken by the `LOG_LEVEL` change in 0.0.12.8.
- Switch to `asyncio`.
- Re-enable browser profile storage.
- Use environment-variable values for global variables when available.
- Wait for the submit button spinner to disappear before proceeding.
- Delete browser profile storage and exit if the username or password phase is repeated more than twice.
- Exit if an incorrect password is detected.
- Log out of Xfinity after processing.
- Dependency updates:
  - Update Playwright from 1.46.0 to 1.47.0.
  - Update `pyee` from 11.1.0 to 12.0.0 in `/xfinity-usage`.
  - Remove the `greenlet` requirement so Playwright can install a compatible version and avoid unnecessary Dependabot PRs.

## 0.0.12.8

- Switch the user agent to Android. Randomly select Android (10-13) and Firefox (120-124) versions.
  - Using a lower Firefox version reduces login and Akamai errors.
- Stop using persistent browser storage.
- Add an exit-code enum to better track exit codes.
- Rename the `LOGLEVEL` add-on variable to `LOG_LEVEL` to match Bashio's log-level variable.
- Improve support for Docker and Kubernetes users ([#36](https://github.com/thor0215/hassio-xfinity-usage/issues/36)).
  - Run Bashio calls in `run.sh` only when Bashio is available.
  - Poll in `xfinity_usage_addon.py` only when Bashio is available.
- Dependency updates:
  - Update the Debian base image to v12.7.
  - Update Playwright from 1.46.0 to 1.47.0 in `/xfinity-usage`.
  - Update `pyee` from 11.1.0 to 12.0.0 in `/xfinity-usage`.
  - Remove the `greenlet` requirement; Playwright installs a compatible version.

## 0.0.12.7.2.2

- Make a second attempt to fix MQTT auto-discovery when the MQTT device has null values ([#22](https://github.com/thor0215/hassio-xfinity-usage/issues/22)).

## 0.0.12.7.2.1

- Exclude the profile folder from backups.

## 0.0.12.7.2

- Log an error if the MQTT server is unreachable.
- Fix the Enable MQTT configuration option.
- Update `debian_12/curl` to v7.88.1-10+deb12u7.
- Provide prebuilt containers ([#23](https://github.com/thor0215/hassio-xfinity-usage/issues/23)).

## 0.0.12.7.1

- Fix MQTT auto-discovery when the MQTT device has null values ([#22](https://github.com/thor0215/hassio-xfinity-usage/issues/22)).
- Add support for MQTT over TLS ([#25](https://github.com/thor0215/hassio-xfinity-usage/issues/25)).

## 0.0.12.7

- Minor code cleanup.
- Create a log file when debug logging is enabled.
- Add two-step verification and Akamai Access Denied detection.
- Use persistent browser storage.
- Remove persistent storage and `xfinity.log` from the `addon_config` folder at startup.
- Stop randomizing the Firefox user agent and version.

## 0.0.12.6

- Switch to the Debian 12 Docker image.
- Add a page-init script to help with bot detection.
- Block Xfinity domains using the EasyPrivacy filter list.
- Set the default page timeout to 60 seconds.
- Update Python modules:
  - Update `typing-extensions` to v4.12.2.
  - Update `tenacity` to v9.0.0.
  - Update PyJWT to v2.9.0.
  - Update Playwright to v1.46.0, which includes Firefox 128.0.

## 0.0.12

- Update the Dockerfile:
  - Update `curl` to v7.81.0-1ubuntu1.17.
  - Update S6 overlay to v3.2.0.0.
- Adjust Playwright to use Desktop Firefox device emulation.

## 0.0.11.1

- Resolve issues with unlimited data plans and xFi Gateway users.

## 0.0.11.0.4

- Work on fixing issues with unlimited data plans and Xfinity WiFi modems.

## 0.0.11

- Add MQTT support.

## 0.0.10.1

- Fix stable branch branding.

## 0.0.10

- Remove the while loop and add an assertion for when usage data is missing from a loaded table.
- Update the Dockerfile to install only the software required by Playwright and Firefox.
- Use Playwright's `expect` API instead of `networkidle` so processing can continue after usage data loads.
- Update the Xfinity authentication URL to `https://www.xfinity.com/learn/internet-service/auth`.
- Add page checks to ensure the page is fully loaded.
- Base session data on the OAuth JWT token.
- Add PyJWT for JWT token processing.
- Encrypt the Xfinity password in debug logs.
- Add the `debug_support` logging option to collect page source and screenshots for troubleshooting.
- Dependency updates:
  - Update Playwright to v1.44.0.
  - Update `typing-extensions` to v4.12.0.
  - Update `pyee` to v11.1.0.
  - Update `greenlet` to v3.0.3.
  - Update `tenacity` to v8.3.0.
  - Update `requests` to v2.32.3.
- Fix issues [#9](https://github.com/thor0215/hassio-xfinity-usage/issues/9) and [#8](https://github.com/thor0215/hassio-xfinity-usage/issues/8).

## 0.0.8

- Add a blueprint to maintain sensor data across Home Assistant restarts.

## 0.0.7

- Add timestamps to log output.
- Write sensor data to a backup file and restore the sensor at startup.
- Add documentation explaining how the sensor works when the add-on is not running.

## 0.0.6

- Add retry logic to prevent infinite page reloads when usage data is missing ([#2](https://github.com/thor0215/hassio-xfinity-usage/issues/2)).

## 0.0.5

- Restart Playwright every 12 hours to recover from uncaught Node.js exceptions that stop processing.

## 0.0.4

- Reformat log output.
- Add comments to explain the code.
- Add English translations for configuration options.

## 0.0.3

- Update the Xfinity logo.

## 0.0.2

- Update the sensor only when the session is active and usage data is available.

## 0.0.1

- Initial release.