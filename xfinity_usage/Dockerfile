# hadolint ignore=DL3006
FROM ghcr.io/hassio-addons/debian-base:9.5.1

# Install the add-on's Python runtime
RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends python3-pip \
    && apt-get clean \
    && rm -fr \
        /tmp/* \
        /var/{cache,log}/* \
        /var/lib/apt/lists/*

# Copy python pip requirements
COPY requirements.txt /

# Install python dependencies
# Create xfinity_usage directory
RUN \
    pip3 install --root-user-action ignore --no-cache-dir \
    --prefer-binary --break-system-packages \
    -r requirements.txt && \
    mkdir -p /xfinity_usage
  
# Copy data for add-on
COPY run.sh /
COPY __init__.py /xfinity_usage/
COPY __main__.py /xfinity_usage/
COPY xfinity_globals.py /xfinity_usage/
COPY xfinity_graphql.py /xfinity_usage/
COPY xfinity_helper.py /xfinity_usage/
COPY xfinity_logger.py /xfinity_usage/
COPY xfinity_mqtt.py /xfinity_usage/
COPY xfinity_token.py /xfinity_usage/
COPY xfinity_my_account.py /xfinity_usage/
COPY xfinity_usage_addon.py /xfinity_usage/
RUN chmod a+x /run.sh

ENV BYPASS="0"

CMD [ "/run.sh" ]

LABEL \
    org.opencontainers.image.title="Xfinity Internet Usage" \
    org.opencontainers.image.description="Xfinity Internet Usage add-on for Home Assistant." \
    org.opencontainers.image.source="https://github.com/thor0215/hassio-xfinity-usage" \
    org.opencontainers.image.licenses="Apache License 2.0"    