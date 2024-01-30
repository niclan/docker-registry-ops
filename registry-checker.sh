#!/bin/bash

# Both these are needed to get a complete check
k8s-inventory.py
registry-checker.py $REGISTRY

