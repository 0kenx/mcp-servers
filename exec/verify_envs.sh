#!/bin/bash
set -e

echo "=== Verifying Development Environments ==="
echo

echo "--- Python Environment ---"
python --version
pip --version
echo "Python environment verified ✓"
echo

echo "--- Node.js/JavaScript/TypeScript Environment ---"
node --version
npm --version
if command -v tsc &> /dev/null; then
    tsc --version
    echo "TypeScript installed ✓"
else
    echo "TypeScript not found ✗"
    exit 1
fi
if command -v yarn &> /dev/null; then
    yarn --version
    echo "Yarn installed ✓"
else
    echo "Yarn not found ✗"
    exit 1
fi
echo "Node.js/JavaScript/TypeScript environment verified ✓"
echo

echo "--- Rust Environment ---"
if command -v rustc &> /dev/null && command -v cargo &> /dev/null; then
    rustc --version
    cargo --version
    rustup --version
    echo "Rust tools installed ✓"
    
    echo "Checking Rust components:"
    if rustup component list --installed | grep -q rustfmt; then
        echo "rustfmt installed ✓"
    else
        echo "rustfmt not found ✗"
        exit 1
    fi
    
    if rustup component list --installed | grep -q clippy; then
        echo "clippy installed ✓"
    else
        echo "clippy not found ✗"
        exit 1
    fi
    
    if rustup component list --installed | grep -q rust-analyzer; then
        echo "rust-analyzer installed ✓"
    else
        echo "rust-analyzer not found ✗"
        exit 1
    fi
    
    if cargo --list | grep -q "cargo-watch"; then
        echo "cargo-watch installed ✓"
    else
        echo "cargo-watch not found ✗"
        exit 1
    fi
else
    echo "Rust environment not properly installed ✗"
    exit 1
fi
echo "Rust environment verified ✓"
echo

echo "--- Go Environment ---"
if command -v go &> /dev/null; then
    go version
    echo "Go environment verified ✓"
else
    echo "Go environment not properly installed ✗"
    exit 1
fi
echo

echo "--- Solidity/Foundry Environment ---"
if command -v forge &> /dev/null; then
    forge --version
    if command -v cast &> /dev/null; then
        cast --version
        echo "Cast installed ✓"
    else
        echo "Cast not found ✗"
        exit 1
    fi
    
    if command -v anvil &> /dev/null; then
        anvil --version
        echo "Anvil installed ✓"
    else
        echo "Anvil not found ✗"
        exit 1
    fi
    echo "Foundry environment verified ✓"
else
    echo "Foundry environment not properly installed ✗"
    exit 1
fi
echo

echo "=== All Development Environments Verified Successfully! ==="
