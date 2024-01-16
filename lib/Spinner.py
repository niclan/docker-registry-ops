#
# Spinner to show progress.
#
# (C) 2024, Nicolai Langfeldt, Schibsted Products and Technology
#

import sys

class Spinner:
    """Spinner to show progress.  Show nothing if we're not on a terminal.

    By default print the spinner character and backspace to so that
    new output on the line will overwrite the spinner character.

    Change this behaviour by setting prefix and postfix:

      sp = Spinner(prefix = "\b", postfix = "")

    This will print backspace then the spinner character, so if something is
    printed it commes after the spinner character on the line.
    
    Silly usage:
      sp = Spinner()

      for i in range(100):
            sp.next()
            time.sleep(0.1)
    """
    
    def __init__(self, prefix = '', postfix = "\b"):
        self.prefix = prefix
        self.postfix = postfix
        self.idx = 0

    def next(self):
        """Print the next spinner character and backspace to so that
        new output on the line will overwrite the spinner character
        """

        # No progress unless we have a terminal
        if not is_tty: return

        self.idx += 1
        if self.idx >= len(spinner): self.idx = 0
        
        print("%s%s" % (self.prefix, spinner[self.idx]),
              end=f'{self.postfix}', flush=True)


# Spinner to show progress
spinner = "|/-\\"

# But only if we have a tty
is_tty = sys.stdout.isatty()
