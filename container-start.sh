#!/bin/bash

# Run inventory script every 15 minutes
cron.py -i 900 -d registry-checker.sh

# And once at startup
registry-checker.sh &

# This is the container anchor. It should not terminate
exec su www-data --shell=/bin/sh -c "while true; do /app/webserver.py; sleep 1; done"
