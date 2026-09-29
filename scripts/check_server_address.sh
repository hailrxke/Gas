#!/bin/bash
# Runs on macOS with Xcode Command Line Tools; no simulator or signing needed.
set -euo pipefail
cd "$(dirname "$0")/.."
check_directory=$(mktemp -d)
trap 'rm -rf "$check_directory"' EXIT
swiftc -D DEBUG Gas/Services/ServerAddress.swift tests/ServerAddressChecks.swift -o "$check_directory/debug-check"
"$check_directory/debug-check"
swiftc Gas/Services/ServerAddress.swift tests/ServerAddressChecks.swift -o "$check_directory/release-check"
"$check_directory/release-check"
