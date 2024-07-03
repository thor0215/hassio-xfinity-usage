#!/command/with-contenv bashio
# shellcheck shell=bash
# shellcheck disable=SC1091

export XFINITY_USERNAME=$(bashio::config "xfinity_username")
export XFINITY_PASSWORD=$(bashio::config "xfinity_password")
export PAGE_TIMEOUT=$(bashio::config "page_timeout")
export LOGLEVEL=$(bashio::config "loglevel")
export POLLING_RATE=$(bashio::config "polling_rate")
export BASHIO_SUPERVISOR_API="${__BASHIO_SUPERVISOR_API}"
export BASHIO_SUPERVISOR_TOKEN="${__BASHIO_SUPERVISOR_TOKEN}"

if bashio::services.available 'mqtt'; then
    bashio::log.green "---"
    bashio::log.yellow "MQTT addon is active on your system!"
    bashio::log.yellow "Add the MQTT details below to the addon configuration :"
    bashio::log.blue "MQTT user : $(bashio::services "mqtt" "username")"
    bashio::log.blue "MQTT password : $(bashio::services "mqtt" "password")"
    bashio::log.blue "MQTT Hostname : $(bashio::services "mqtt" "host")"
    bashio::log.blue "MQTT Port : $(bashio::services "mqtt" "port")"
    bashio::log.green "---"
fi

[[ $(bashio::config "mqtt_enabled") != null ]] && export MQTT_SERVICE=$(bashio::config "mqtt_enabled")
[[ $(bashio::config "mqtt_username") != null ]] && export MQTT_USERNAME=$(bashio::config "mqtt_username")
[[ $(bashio::config "mqtt_password") != null ]] && export MQTT_PASSWORD=$(bashio::config "mqtt_password")
[[ $(bashio::config "mqtt_host") != null ]] && export MQTT_HOST=$(bashio::config "mqtt_host")
[[ $(bashio::config "mqtt_port") != null ]] && export MQTT_PORT=$(bashio::config "mqtt_port")


if [ "${LOGLEVEL}" == "debug" ] || [ "${LOGLEVEL}" == "debug_support" ]; then
    python3 --version
    python3 -m pip list
    ls -al /config
fi

python3 -Wignore xfinity_usage_addon.py
