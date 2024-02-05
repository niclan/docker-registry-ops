import os
import sys
from pathlib import Path
from signal import signal

# The signal handler must be a global function, so we need a global
# context to hold the instance of the class that will handle the signal
alarm_instance = None
orig_alarm_handler = None
alarm_setup = False


def _handle_alarm(signum, frame):
    """Signal handlers must be global and must take two arguments."""
    
    alarm_instance.handle_alarm(signum, frame)

class Restarter:
    def if_file_change(self, files = None):
        """Set up so that if any of the files in the list has changed,
        restart the process. Call this as many times as you like."""

        if self.watching is None:
            # Insert the program and all the modules - the program itself
            # is in the module list
            self.watching = []
            for m in sys.modules.keys():
                module = sys.modules[m]
                if hasattr(module, "__file__"): self.watching.append(mo.__file__)

        if files is not None:

            # Make files a array if it is a string
            if type(files).__name__ == 'str': files = [ files ]

            # Make all paths absolute
            files = [ Path(p).absolute() for p in files ]

            # Add named file and make sure there is only one instance of each file
            self.watching.extend(files)
            
        self.watching = list(set(self.watching))


    def check_files(self):
        """Check if any of the watched files has changed and restart if so."""

        if self.watching is None:
            return

        for f in self.watching:
            if os.path.getmtime(f) > self.start_time:
                self.restart()


class Child(Restarter)
    def __init__(self):
        self.argv = sys.argv.copy()
        self.watching = None    # Files we're watching for changes
        self.sleep_interval = 1 # Sleep interval for checking files
        self.childPid = None    # Child process PID

    def start():
        process

    def if_file_change(self, files = None):
        """Set up so that if any of the files in the list has changed,
        restart the process. Call this as many times as you like."""

        if self.watching is None:
            # Insert the program and all the modules - the program itself
            # is in the module list
            self.watching = []
            for m in sys.modules.keys():
                module = sys.modules[m]
                if hasattr(module, "__file__"): self.watching.append(mo.__file__)

        if files is not None:

            # Make files a array if it is a string
            if type(files).__name__ == 'str': files = [ files ]

            # Make all paths absolute
            files = [ Path(p).absolute() for p in files ]

            # Add named file and make sure there is only one instance of each file
            self.watching.extend(files)
            
        self.watching = list(set(self.watching))


    def check_files(self):
        """Check if any of the watched files has changed and restart if so."""

        if self.watching is None:
            return

        for f in self.watching:
            if os.path.getmtime(f) > self.start_time:
                self.restart()


class Me(Restarter):
    """Somewhat minimal class to restart the process on SIGHUP, or if
    some file has changed

    Usage:
        import signal
        import Restart
    
        restart = Restart.Me(signal.SIGHUP)

        # Watch for changes in the file - if it changes, restart
        # automatically All the files that make up the program and the
        # modules is uses are watched as well.
        restart.if_file_change("/etc/myconfig")

        # Make this call to get the files checked when convenient
        restart.check_files()

        # Make this call to schedule a automatic check every n =1
        # seconds.  This uses the OS alarm(1)/SIGALARM service and replaces
        # any previous signal handlers.  This alarm will auto-repeat
        restart.scheduled_check_files(1)

    The class initalizer saves the current argv and sets up the needed
    signal handlers.

    NOTE: Call before calling argparse or similar that changes sys.argv.

    """

    def __init__(self, signal):
        self.argv = sys.argv.copy()
        self.watching = None    # Files we're watching for changes
        self.alarm_interval = 0 # Alarm interval for checking files
        self.orig_alarm_handler = None

        signal(signal, self.restart)

        
    def restart(self):
        print("Received SIGHUP, restarting", self.argv)

        os.execv(__file__, self.argv)


    def if_file_change(self, files = None):
        """Set up so that if any of the files in the list has changed,
        restart the process. Call this as many times as you like."""

        if self.watching is None:
            # Insert the program and all the modules - the program itself
            # is in the module list
            self.watching = []
            for m in sys.modules.keys():
                module = sys.modules[m]
                if hasattr(module, "__file__"): self.watching.append(mo.__file__)

        if files is not None:

            # Make files a array if it is a string
            if type(files).__name__ == 'str': files = [ files ]

            # Make all paths absolute
            files = [ Path(p).absolute() for p in files ]

            # Add named file and make sure there is only one instance of each file
            self.watching.extend(files)
            
        self.watching = list(set(self.watching))


    def check_files(self):
        """Check if any of the watched files has changed and restart if so."""

        if self.watching is None:
            return

        for f in self.watching:
            if os.path.getmtime(f) > self.start_time:
                self.restart()


    def handle_alarm(self, signum, frame):
        self.check_files()
        signal.alarm(self.alarm_interval)

                
    def scheduled_check_files(self, interval):
        """Set up scheduled checking of the files.  This replaces any
        previously installed SIGALRM handler with our own.

        # Check every second
        restart.scheduled_check_files(1)

        # Disable, and reinstall original signal handler
        restart.scheduled_check_files(0)

        """

        self.alarm_interval = interval

        if interval == 0:
            alarm(0)

            if alarm_setup:
            signal(signal.SIGALRM, orig_alarm_handler)
            self.orig_alarm_handler = None
            return
            

        if self.signal_setup is None:
            signal(signal.SIGALRM, self.handle_alarm)
        
        signal.alarm(self.alarm_interval)

        self.check_files()
        self.schedule_check()
