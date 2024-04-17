# This is a library file with common code for the keep rules.

import re
import sys
import json

"""The rules are loaded from
images-keep.json and are used to decide if a tag should be kept or not.

Usage:
   from keeprules import *

The module declares the following functions and variables:

* keeprules: A list of rules that are loaded from images-keep.json
* keep_by_rule(repo_name, tag): Check if a tag should be kept by a rule
* keep_repo_by_rule(repo_name): Check if a repo should be kept by a rule
* load_keep_list(): Load the rules from images-keep.json
"""

# Keep rule enforcement

keeprules = []


def keep_by_rule(repo_name, tag):
    """Check if a tag should be kept by a rule.  This function has the
    most sanity checks (compared to keep_repo_by_rule) and should be
    called to validate the ruleset after loading it. Just pass a
    illegal repo_name which can't be matched and the whole rule sett
    will be itterated."""

    for rule in keeprules:
        if rule is None:
            sys.exit("Rule is None??")
        if not isinstance(rule, dict):
            sys.exit("Rule %s is not a dict" % rule)
        if "pattern" in rule:
            if re.match(rule["pattern"], repo_name):
                if "keep" in rule:
                    if rule["keep"] == "all":
                        return True
                    if rule["keep"] == "latest" and tag == "latest":
                        return True
                
                else:
                    sys.exit("Pattern rule without keep: %s" % rule)
        else:
            sys.exit("Rule without pattern: %s" % rule)

    return False


def keep_repo_by_rule(repo_name):
    """Check if something in a repo should be kept by a rule, so that all the tags
    must be checked against the ruleset"""

    for rule in keeprules:
        if "pattern" in rule:
            if not "keep" in rule:
                sys.exit("Pattern rule without keep: %s" % rule)
            if rule["keep"] == "none":
                return False
            return re.match(rule["pattern"], repo_name)
        else:
            sys.exit("Rule without pattern: %s" % rule)

    return False


def load_keep_list():
    """Load images-keep.json file with the list of images we want to
    keep. The rules is loaded into the global keeprules variable"""

    global keeprules

    # Check if file exists, and if it is valid JSON
    try:
        with open("images-keep.json", "r") as f:
            keeprules = json.loads(f.read())

    except FileNotFoundError:
        print("images-keep.json not found", file=sys.stderr)
        return

    except json.decoder.JSONDecodeError:
        sys.exit("images-keep.json file is not valid JSON")

    print("Loaded %d keep rules from images-keep.json" % len(keeprules), file=sys.stderr)

    # Some simple sanity checks
    if keeprules is None:
        keeprules = []
    if not isinstance(keeprules, list):
        sys.exit("images-keep.json file is not a list")
        
    # make a call to check if ruleset is valid, function exits if not
    keep_by_rule("This:invalid:repository:name:wont:be:matched", "test")


    # We should not really get here
    return

