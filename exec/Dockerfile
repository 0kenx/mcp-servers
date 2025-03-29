# First, build the application in the `/app` directory.
# See `Dockerfile` for details.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Disable Python downloads, because we want to use the system interpreter
# across both images. If using a managed Python version, it needs to be
# copied from the build image into the final image; see `standalone.Dockerfile`
# for an example.
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Then, use a final image without uv
FROM python:3.12-slim-bookworm
# It is important to use the image that matches the builder, as the path to the
# Python executable must be the same, e.g., using `python:3.11-slim-bookworm`
# will fail.

# Install system dependencies and common tools
RUN apt-get update && \
    apt-get install -yq --no-install-recommends \
        build-essential \
        git \
        curl \
        wget \
        ripgrep \
        nano \
        jq \
        zip \
        unzip \
        ca-certificates \
        gnupg \
        lsb-release \
        software-properties-common \
        apt-transport-https \
        nodejs \
        npm \
        less \
        iproute2 \
        net-tools \
        iputils-ping \
        dnsutils \
        gnupg \
        openssh-client \
        pkg-config \
        libssl-dev \
        cmake \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Change user to non-root
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Create the user
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    #
    # [Optional] Add sudo support. Omit if you don't need to install software after connecting.
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Copy the application from the builder
COPY --from=builder --chown=$USERNAME:$USERNAME /app /app

# Make sure the user owns their home directory and tools
RUN chown -R $USERNAME:$USERNAME /home/$USERNAME

# Set working directory
WORKDIR /app

# Change to the regular user
USER $USERNAME

# Install Rust (rustup and cargo)
#RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y && \
#    echo 'source "$HOME/.cargo/env"' >> /home/$USERNAME/.bashrc
#RUN $HOME/.cargo/bin/rustup component add rustfmt clippy rust-analyzer && \
#    $HOME/.cargo/bin/cargo install cargo-watch

# Install Python tools and packages
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
    ipython \
    requests \
    pandas \
    numpy \
    matplotlib \
    seaborn \
    black \
    flake8 \
    mypy \
    pytest

# Install Go
#RUN curl -OL https://golang.org/dl/go1.24.1.linux-amd64.tar.gz && \
#    tar -C /usr/local -xzf go1.24.1.linux-amd64.tar.gz && \
#    rm go1.24.1.linux-amd64.tar.gz && \
#    echo 'export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin' >> /home/$USERNAME/.bashrc


# Set environment variables
ENV PATH="/app/.venv/bin:/home/$USERNAME/.cargo/bin:/usr/local/go/bin:/home/$USERNAME/go/bin:$PATH"

ENTRYPOINT ["python", "/app/src/exec.py"]
