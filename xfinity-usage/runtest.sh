#!/command/with-contenv bashio
# shellcheck shell=bash
# shellcheck disable=SC1091

echo "Xfinity Usage" 
export XFINITY_USERNAME="bthoreson"
export XFINITY_PASSWORD="ApJMoquwGu*tEE%a6nvJ"
export PAGE_TIMEOUT=45
export LOGLEVEL="debug"
export POLLING_RATE=60

if [ "${LOGLEVEL}" == "debug" ]; then
    python3 --version
    python3 -m pip list
fi

python3 -Wignore xfinity_usage_addon.py
