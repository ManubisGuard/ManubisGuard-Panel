#!/bin/bash

# The legacy TUI entry point is kept for CLI compatibility.
# The application now exposes its management interface through the CLI.
exec /usr/bin/manubisguard-cli "$@"
