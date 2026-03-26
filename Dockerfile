# To Build Docker (Multi-arch) with Podman
# podman machine ssh "sudo podman run --privileged --rm docker.io/multiarch/qemu-user-static --reset -p yes"
# podman run --rm --privileged docker.io/tonistiigi/binfmt --install all
#
# podman manifest rm rafflesg/nanobot:latest 2>$null
# podman build --platform linux/amd64,linux/arm64 --manifest rafflesg/nanobot:latest .
# podman manifest push --all rafflesg/nanobot:latest docker://docker.io/rafflesg/nanobot:latest

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set environment variable to suppress SyntaxWarnings
ENV PYTHONWARNINGS="ignore::SyntaxWarning"

# Install Node.js 20 for the WhatsApp bridge and ffmpeg for audio processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg git tmux ffmpeg openssh-client && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs gh && \
    apt-get purge -y gnupg && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cached layer)
COPY pyproject.toml README.md LICENSE ./
RUN mkdir -p nanobot bridge && touch nanobot/__init__.py && \
    uv pip install --system --no-cache . && \
    rm -rf nanobot bridge

# Copy the full source and install
COPY nanobot/ nanobot/
COPY bridge/ bridge/
RUN uv pip install --system --no-cache .

# Build the WhatsApp bridge
RUN git config --global url."https://github.com/".insteadOf "ssh://git@github.com/"

WORKDIR /app/bridge
RUN npm install && npm run build
WORKDIR /app

# Create config directory
RUN mkdir -p /root/.nanobot

# Gateway default port
EXPOSE 18790

ENTRYPOINT ["nanobot"]
CMD ["status"]
