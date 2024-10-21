#!/command/with-contenv bashio
# shellcheck shell=bash
# shellcheck disable=SC1091

export HEADLESS=True

# Issue #36 add support for non Home Assistant deployments
if [ $BYPASS = "0" ]; then
    export XFINITY_USERNAME=$(bashio::config "xfinity_username")
    export XFINITY_PASSWORD=$(bashio::config "xfinity_password")
    export PAGE_TIMEOUT=$(bashio::config "page_timeout")
    export LOG_LEVEL=$(bashio::config "log_level")
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
    [[ $(bashio::config "mqtt_password") == null ]] && export MQTT_PASSWORD=$(bashio::services "mqtt" "password") 
    [[ $(bashio::config "mqtt_host") != null ]] && export MQTT_HOST=$(bashio::config "mqtt_host")
    [[ $(bashio::config "mqtt_port") != null ]] && export MQTT_PORT=$(bashio::config "mqtt_port")
    [[ $(bashio::config "mqtt_raw_usage") != null ]] && export MQTT_RAW_USAGE=$(bashio::config "mqtt_raw_usage")
    [[ $(bashio::config "debug_support") != null ]] && export DEBUG_SUPPORT=$(bashio::config "debug_support")


    if [ "${LOG_LEVEL}" == "debug" ] || [ "${LOG_LEVEL}" == "debug_support" ]; then
        python3 --version
        python3 -m pip list
        ls -al /config
    fi

    POLLING_RATE=0
    while python3 -Wignore /xfinity_usage_addon.py; do 
        bashio::log.info "Sleeping for $(bashio::config "polling_rate") seconds"
        sleep $(bashio::config "polling_rate")s; 
    done
else
    #xvfb-run python3 -Wignore xfinity_usage_addon.py # Headed mode
    python3 -Wignore /xfinity_usage_addon.py

fi
