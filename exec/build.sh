#!/bin/bash
set -e

# Define image name
IMAGE_NAME="mcp-exec"

echo "Building Docker image: ${IMAGE_NAME}"

# Build the Docker image
docker build -t ${IMAGE_NAME} .

echo "Build complete!"
echo "----------------------------------------"
echo "You can run the container with:"
echo "docker run -it --rm ${IMAGE_NAME} bash"
echo ""
echo "To test the installed environments, run:"
echo "docker run -it --rm ${IMAGE_NAME} /bin/bash -c 'python -V && \
node -v && \
npm -v && \
tsc -v && \
cargo --version && \
rustc --version && \
go version && \
forge --version'"
