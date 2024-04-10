.PHONEY: container run standalone shell default secret dev stage prod

PORCELAIN = $(shell git status --porcelain)

default:
	@echo
	@echo Use one of these targets:
	@echo
	@echo "  webserver  - Run the webserver in the local environment"
	@echo "  container  - build a container"
	@echo "  run        - Run the container with redirect from 8080 on localhost to"
	@echo "               apache inside.  You probably want to make \"standalone\" first"
	@echo "  shell      - Start a shell in the container to inspect it"
	@echo
	@echo "These deploys to kubernetes:"
	@echo "  dev        - Make secret file and run skaffold dev"
	@echo "  staging    - Make secret file and run skaffold run -p staging"
	@echo "  prod       - Make secret file and run skaffold run -p prod"
	@echo "  secret     - Create the secret file for the vault"
	@echo
	@echo "Notes:"
	@echo " * making secrets requires setting VAULT_ADDR and then VAULT_TOKEN or"
	@echo "   doing vault login (see also vault/Makefile)"
	@echo " * making stage or prod requires a clean git status/git commit"
	@echo " * make webserver requires running first './k8s-inventory.py' and then"
	@echo "   './registry-checker.py' and then doing"
	@echo "   'REPORTDIR=./check-report-<something> make webserver'"
	@echo

webserver:
	export PYTHONLIB=${PWD}/lib
	./app/webserver.py

container:
	docker build -t docker-registry-checker .

run: container
	docker container run -p 8000:80 --rm -it docker-registry-checker:latest

# Build container (jenkins like) or standalone (looks like kubernetes
# env, isn't) first
shell:	container
	docker container run --rm -it docker-registry-checker:latest /bin/bash

secret:
	(cd vault && make secrets)

# In my example dev runs in the stage namespace
dev:	secret
	skaffold dev

stage:
	@echo Please use "make staging" instead of "make stage"

staging: secret
	skaffold run -p staging

prod:	secret
	@if [ -n "$(PORCELAIN)" ]; then echo "Commit everything before a production push, aborting"; exit 1; fi
	skaffold run -p prod

vglabprod:
	@if [ -n "$(PORCELAIN)" ]; then echo "Commit everything before a production push, aborting"; exit 1; fi
	skaffold run -p vglabprod
