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

if [ "${LOGLEVEL}" == "debug" ] || [ "${LOGLEVEL}" == "debug_support" ]; then
    python3 --version
    python3 -m pip list
    ls -al /config
fi

python3 -Wignore xfinity_usage_addon.py
