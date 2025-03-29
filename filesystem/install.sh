#!/bin/bash

# Exit on error
set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Source script path
SOURCE_SCRIPT="$SCRIPT_DIR/cli/mcpdiff.py"

# Check if source script exists
if [ ! -f "$SOURCE_SCRIPT" ]; then
    echo "Error: Source script not found at $SOURCE_SCRIPT"
    exit 1
fi

# List of possible installation directories in order of preference
INSTALL_DIRS=(
    "$HOME/.local/bin"
    "/usr/local/bin"
    "/opt/local/bin"
    "/usr/bin"
)

# Find the first directory that exists and is in PATH
DEST_DIR=""
for dir in "${INSTALL_DIRS[@]}"; do
    if [ -d "$dir" ] && [[ ":$PATH:" == *":$dir:"* ]]; then
        DEST_DIR="$dir"
        break
    fi
done

# If no suitable directory found, try to create ~/.local/bin
if [ -z "$DEST_DIR" ]; then
    DEST_DIR="$HOME/.local/bin"
    mkdir -p "$DEST_DIR"
    # Add to PATH if not already there
    if [[ ":$PATH:" != *":$DEST_DIR:"* ]]; then
        echo "export PATH=\"\$PATH:$DEST_DIR\"" >> "$HOME/.bashrc"
        echo "export PATH=\"\$PATH:$DEST_DIR\"" >> "$HOME/.zshrc"
        echo "Added $DEST_DIR to PATH in .bashrc and .zshrc"
    fi
fi

# Destination path
DEST_BIN="$DEST_DIR/mcpdiff"

# Create shell wrapper
echo "Installing mcpdiff to $DEST_BIN..."
cat > "$DEST_BIN" << EOF
#!/bin/bash
python3 "$SOURCE_SCRIPT" "\$@"
EOF
chmod +x "$DEST_BIN"

# Verify installation
if [ -f "$DEST_BIN" ] && [ -x "$DEST_BIN" ]; then
    echo "Installation successful! mcpdiff is now available in your PATH."
    echo "You can run it by typing 'mcpdiff' from any directory."
    echo "Note: You may need to restart your shell for PATH changes to take effect."
else
    echo "Error: Installation failed"
    exit 1
fi 