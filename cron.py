#!/usr/bin/env python3
#
# cron.py: Script to run the some command at regular intervals.
# This is a simple wrapper around the python sched module and is
# meant to be used in containers and pods by using stdout/stderr to log
# so it logs into the container/pod log.
#
# (C) 2024, Nicolai Langfeldt, Schibsted Products and Technology
#

import os
import sys
import argparse
import sched
import time

def daemonize():
    """Simplest possible forking to background process"""
    try:
        pid = os.fork()
        if pid != 0:
            # Exit first parent
            sys.exit(0)

    except OSError as e:
        print("Fork failed: %d (%s)" % (e.errno, e.strerror))
        sys.exit(1)

    

def execute_task():
    global task
    
    try:
        print("Running %s" % task)
        os.system(task)
    except e:
        print("Failed to run %s" % task)
        print("Exeception: %s" % str(e))


def repeat_task():
    global interval, scheduler
    
    scheduler.enter(interval, 1, execute_task, ())
    scheduler.enter(interval, 1, repeat_task, ())


def main():
    parser = argparse.ArgumentParser(description='Run a task at regular intervals')
    parser.add_argument('-i', '--interval', action='store', type=int, \
                        default=60*5, help='Interval in seconds, default is 300 = 5 minutes')
    parser.add_argument('-d', '--daemon', action='store_true', default=False, \
                        help='Daemonize the process, default is to stay in foreground')
    parser.add_argument('command', help='Command to run')
    args = parser.parse_args()

    if args.command is None:
        print("No command given")
        sys.exit(1)

    global task, interval, scheduler

    task = args.command
    interval = args.interval

    print("Running k8s-inventory.py every %d seconds" % interval)

    if args.daemon:
        print("Daemonizing cron.py")
        daemonize()

    scheduler = sched.scheduler(time.time, time.sleep)

    repeat_task()

    scheduler.run()


if __name__ == "__main__":
    main()
