#
# Spinner to show progress.
#
# (C) 2024, Nicolai Langfeldt, Schibsted Products and Technology
#

import sys
import random

class Spinner:
    """Spinner to show progress.  Show nothing if we're not on a terminal.

    By default print the spinner character and backspace to so that
    new output on the line will overwrite the spinner character.

    Change this behaviour by setting prefix and postfix:

      sp = Spinner(prefix = "\b", postfix = "")

    This will print backspace then the spinner character, so if something is
    printed it comes after the spinner character on the line.

    There are 4 kinds of spinners.  The default is picked at random.  See
    the kind method for more information and to set one specific one.
    
    Silly usage:
      sp = Spinner()

      for i in range(100):
            sp.next()
            time.sleep(0.1)
    """
    
    def __init__(self, prefix = '', postfix = "\b", kind = None):
        self.prefix = prefix
        self.postfix = postfix
        self.idx = 0
        
        if kind is None:
            kind = random.randint(0, len(spinner)-1)

        self.kind(kind)


    def random_kind(self):
        """Change the spinner kind to a random one."""
        import random
        self.kind(random.randint(0, len(spinner)-1))
        self.idx = 0


    def kind(self, new_kind):
        """Change the spinner kind.  There are three kinds of spinners:
        - 0: |/-\      - Looks like a spinning line
        - 1: .oOo      - Looks like a pulsing dot
        - 2: ⠇⠋⠙⠸⠴⠦  - Looks like a line spinning in a square,
                         kindly suggested by copilot, thanks!
        - 3: odoqopod  - Looks like a circle with issues

        Number 2 is actually braile characters in UTF-8. So it
        might not work on your terminal.

        If you give a number outside the defined range it will be set
        to 0.

        """
        self.kind = new_kind
        if self.kind >= len(spinner): self.kind = 0
        if self.kind < 0: self.kind = 0


    def next(self):
        """Print the next spinner character and backspace to so that
        new output on the line will overwrite the spinner character
        """

        # No progress unless we have a terminal
        if not is_tty: return

        self.idx += 1
        if self.idx >= len(spinner[self.kind]): self.idx = 0
        
        print("%s%s" % (self.prefix, spinner[self.kind][self.idx]),
              end=f'{self.postfix}', flush=True)


# Spinner to show progress
spinner = [ "|/-\\", ".oOo", "⠇⠋⠙⠸⠴⠦", "-+|+", "odoqopod" ]
# But only if we have a tty
is_tty = sys.stdout.isatty()
