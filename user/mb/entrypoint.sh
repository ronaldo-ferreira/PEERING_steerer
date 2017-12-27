#!/usr/bin/dumb-init /bin/bash
set -e

source bird-sh.source
start_bird "$@"
