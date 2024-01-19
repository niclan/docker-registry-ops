#!/bin/bash

cron -f -L 15 &

# This is the container anchor script. It should not terminate
exec su www-data --shell=/bin/sh -c "exec /app/webserver.py"
