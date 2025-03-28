#!/bin/bash

# Build the Docker image
docker build -t mcp-exec .

echo "Build complete. Run with: docker run -p 8080:8080 mcp-exec"
