ARG BUILD_FROM=debian:12.7-slim
# hadolint ignore=DL3006
FROM ${BUILD_FROM}

# Environment variables
ENV \
    CARGO_NET_GIT_FETCH_WITH_CLI=true \
    DEBIAN_FRONTEND="noninteractive" \
    HOME="/root" \
    LANG="C.UTF-8" \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1 \
    PS1="$(whoami)@$(hostname):$(pwd)$ " \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    S6_BEHAVIOUR_IF_STAGE2_FAILS=2 \
    S6_CMD_WAIT_FOR_SERVICES_MAXTIME=0 \
    S6_CMD_WAIT_FOR_SERVICES=1 \
    YARN_HTTP_TIMEOUT=1000000 \
    TERM="xterm-256color"

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install base system
ARG BUILD_ARCH=amd64
ARG BASHIO_VERSION="v0.16.2"
ARG S6_OVERLAY_VERSION="3.2.0.0"
ARG TEMPIO_VERSION="2021.09.0"
RUN \
    apt-get update \
    \
    && apt-get install -y --no-install-recommends \
        bash=5.2.15-2+b7 \
        ca-certificates=20230311 \
        curl \
        jq=1.6-2.1 \
        tzdata=2024a-0+deb12u1 \
        xz-utils=5.4.1-0.2 \
        libxcb-shm0\
        libx11-xcb1 \
        libx11-6 \
        libxcb1 \
        libxext6 \
        libxrandr2 \
        libxcomposite1 \
        libxcursor1 \
        libxdamage1 \
        libxfixes3 \
        libxi6 \
        libgtk-3-0 \
        libpangocairo-1.0-0 \
        libpango-1.0-0 \
        libatk1.0-0 \
        libcairo-gobject2 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libglib2.0-0 \
        libasound2 \
        libxrender1 \
        libfreetype6 \
        libfontconfig1 \
        libdbus-1-3 \
        python3-pip \
        xauth \
        xvfb \
    \
    && c_rehash \
    \
    && S6_ARCH="${BUILD_ARCH}" \
    && if [ "${BUILD_ARCH}" = "i386" ]; then S6_ARCH="i686"; \
    elif [ "${BUILD_ARCH}" = "amd64" ]; then S6_ARCH="x86_64"; \
    elif [ "${BUILD_ARCH}" = "armv7" ]; then S6_ARCH="arm"; fi \
    \
    && curl -L -s "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz" \
        | tar -C / -Jxpf - \
    \
    && curl -L -s "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_ARCH}.tar.xz" \
        | tar -C / -Jxpf - \
    \
    && curl -L -s "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-symlinks-noarch.tar.xz" \
        | tar -C / -Jxpf - \
    \
    && curl -L -s "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-symlinks-arch.tar.xz" \
        | tar -C / -Jxpf - \
    \
    && mkdir -p /etc/fix-attrs.d \
    && mkdir -p /etc/services.d \
    \
    && curl -J -L -o /tmp/bashio.tar.gz \
        "https://github.com/hassio-addons/bashio/archive/${BASHIO_VERSION}.tar.gz" \
    && mkdir /tmp/bashio \
    && tar zxvf \
        /tmp/bashio.tar.gz \
        --strip 1 -C /tmp/bashio \
    \
    && mv /tmp/bashio/lib /usr/lib/bashio \
    && ln -s /usr/lib/bashio/bashio /usr/bin/bashio \
    \
    && curl -L -s -o /usr/bin/tempio \
        "https://github.com/home-assistant/tempio/releases/download/${TEMPIO_VERSION}/tempio_${BUILD_ARCH}" \
    && chmod a+x /usr/bin/tempio \
    \
    && apt-get purge -y --auto-remove \
        xz-utils \
    && apt-get clean \
    && rm -fr \
        /tmp/* \
        /var/{cache,log}/* \
        /var/lib/apt/lists/*

# Copy root filesystem
COPY rootfs /

# Copy s6-overlay adjustments
COPY s6-overlay /package/admin/s6-overlay-${S6_OVERLAY_VERSION}/

# Entrypoint & CMD
ENTRYPOINT [ "/init" ]

# Build arugments
ARG BUILD_DATE
ARG BUILD_REF
ARG BUILD_VERSION
ARG BUILD_REPOSITORY

# Labels
LABEL \
    io.hass.name="Addon Debian base for ${BUILD_ARCH}" \
    io.hass.description="Home Assistant Community Add-on: ${BUILD_ARCH} Debian base image" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="base" \
    io.hass.version=${BUILD_VERSION} \
    io.hass.base.version=${BUILD_VERSION} \
    io.hass.base.name="debian" \
    io.hass.base.image="hassioaddons/debian-base" \
    maintainer="Franck Nijhof <frenck@addons.community>" \
    org.opencontainers.image.title="Addon Debian base for ${BUILD_ARCH}" \
    org.opencontainers.image.description="Home Assistant Community Add-on: ${BUILD_ARCH} Debian base image" \
    org.opencontainers.image.vendor="Home Assistant Community Add-ons" \
    org.opencontainers.image.authors="Franck Nijhof <frenck@addons.community>" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://addons.community" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}
    
# Allow playwright to run in headed mode
#RUN apt-get update \
#    && apt-get install -y --no-install-recommends \
#        xvfb
    
COPY requirements.txt /
RUN pip3 install --upgrade --break-system-packages pip && \
    pip3 install --no-cache-dir \
  --prefer-binary --break-system-packages \
  -r requirements.txt \
  playwright==1.49.1 \
  playwright-stealth==1.0.6

RUN playwright install firefox
  
# Copy data for add-on
COPY run.sh /
COPY secret.key /
COPY xfinity_globals.py /
COPY xfinity_graphql.py /
COPY xfinity_helper.py /
COPY xfinity_logger.py /
COPY xfinity_mqtt.py /
COPY xfinity_token.py /
COPY xfinity_usage_addon.py /
COPY xfinity_web_auth.py /
RUN chmod a+x /run.sh

# Issue #36 add support for non Home Assistant deployments
ENV BYPASS="0"

CMD [ "/run.sh" ]

# Bits for running as xfinity user
#RUN useradd -mr -d /var/cache/xfinity -s /sbin/nologin xfinity
#COPY run.sh /var/cache/xfinity
#COPY xfinity_usage_addon.py /var/cache/xfinity
#RUN chmod a+x /var/cache/xfinity/run.sh
#RUN chown xfinity:xfinity -R /var/cache/xfinity

#USER xfinity
#RUN cd /var/cache/xfinity && playwright install firefox

#USER root
#CMD [ "/var/cache/xfinity/run.sh" ]

