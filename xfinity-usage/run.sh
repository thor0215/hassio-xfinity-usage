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
    bashio::log.yellow "MQTT addon is active on your system! Add the MQTT details below to the Birdnet-go config.yaml :"
    bashio::log.blue "MQTT user : $(bashio::services "mqtt" "username")"
    bashio::log.blue "MQTT password : $(bashio::services "mqtt" "password")"
    bashio::log.blue "MQTT broker : tcp://$(bashio::services "mqtt" "host"):$(bashio::services "mqtt" "port")"
    bashio::log.green "---"

    export MQTT_USER=$(bashio::services "mqtt" "username")
    export MQTT_PASSWORD=$(bashio::services "mqtt" "password")
    export MQTT_HOST=$(bashio::services "mqtt" "host"):
    export MQTT_PORT=$(bashio::services "mqtt" "port")

fi

if [ "${LOGLEVEL}" == "debug" ] || [ "${LOGLEVEL}" == "debug_support" ]; then
    python3 --version
    python3 -m pip list
    ls -al /config
fi

python3 -Wignore xfinity_usage_addon.py
