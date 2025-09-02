# Optimized 2-stage Docker build for Zulip
# Stage 1: Build environment with caching optimizations
FROM ubuntu:24.04 AS base

# Set up working locales and upgrade the base image
ENV LANG="C.UTF-8"

ARG UBUNTU_MIRROR

# Optimize package installation with better caching
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    { [ ! "$UBUNTU_MIRROR" ] || sed -i "s|http://\(\w*\.\)*archive\.ubuntu\.com/ubuntu/\? |$UBUNTU_MIRROR |" /etc/apt/sources.list; } && \
    apt-get -q update && \
    apt-get -q dist-upgrade -y && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get -q install --no-install-recommends -y \
        ca-certificates \
        git \
        locales \
        python3 \
        sudo \
        tzdata \
        openssl \
        xxd \
        curl \
        build-essential && \
    touch /var/mail/ubuntu && chown ubuntu /var/mail/ubuntu && userdel -r ubuntu && \
    useradd -d /home/zulip -m zulip -u 1000

FROM base AS build

RUN echo 'zulip ALL=(ALL:ALL) NOPASSWD:ALL' >> /etc/sudoers

USER zulip
WORKDIR /home/zulip

# Copy source code instead of cloning to improve build speed and caching
COPY --chown=zulip:zulip . ./zulip/

WORKDIR /home/zulip/zulip

ARG CUSTOM_CA_CERTIFICATES
ARG ZULIP_GIT_REF=11.0

# Set git ref for build process
RUN git config --global user.email "docker@zulip.com" && \
    git config --global user.name "Docker Build" && \
    git init . && \
    git add . && \
    git commit -m "Docker build snapshot" || true

# Optimize build process with caching and parallel operations
RUN --mount=type=cache,target=/home/zulip/.cache,uid=1000,gid=1000 \
    --mount=type=cache,target=/tmp,uid=1000,gid=1000 \
    SKIP_VENV_SHELL_WARNING=1 ./tools/provision --build-release-tarball-only && \
    uv run --no-sync ./tools/build-release-tarball docker && \
    mv /tmp/tmp.*/zulip-server-docker.tar.gz /tmp/zulip-server-docker.tar.gz

# Stage 2: Production image with optimized installation
FROM base

ENV DATA_DIR="/data"

# Copy the release tarball from build stage
COPY --from=build /tmp/zulip-server-docker.tar.gz /root/

ARG CUSTOM_CA_CERTIFICATES

# Optimize installation process with better layer caching
RUN dpkg-divert --add --rename /etc/init.d/nginx && \
    ln -s /bin/true /etc/init.d/nginx

RUN mkdir -p "$DATA_DIR"

RUN cd /root && \
    tar -xf zulip-server-docker.tar.gz && \
    rm -f zulip-server-docker.tar.gz && \
    mv zulip-server-docker zulip

# Install Zulip with caching
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    /root/zulip/scripts/setup/install \
      --hostname="$(hostname)" \
      --email="docker-zulip" \
      --puppet-classes="zulip::profile::docker" \
      --postgresql-version=14

# Clean up in separate layer for better caching
RUN rm -f /etc/zulip/zulip-secrets.conf /etc/zulip/settings.py && \
    apt-get -qq autoremove --purge -y && \
    apt-get -qq clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY entrypoint.sh /sbin/entrypoint.sh
COPY scripts/setup/configure-cloudrun-settings /root/zulip/scripts/setup/configure-cloudrun-settings
COPY scripts/setup/configure-cloudrun-secrets /root/zulip/scripts/setup/configure-cloudrun-secrets

# Make scripts executable
RUN chmod +x /sbin/entrypoint.sh \
    /root/zulip/scripts/setup/configure-cloudrun-settings \
    /root/zulip/scripts/setup/configure-cloudrun-secrets

VOLUME ["$DATA_DIR"]
EXPOSE 25 80 443

ENTRYPOINT ["/sbin/entrypoint.sh"]
CMD ["app:run"]