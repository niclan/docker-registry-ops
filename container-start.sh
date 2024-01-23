#!/bin/bash

cron.py -i 900 -d k8s-inventory.py

# This is the container anchor script. It should not terminate
exec su www-data --shell=/bin/sh -c "exec /app/webserver.py"
