.PHONEY: tokenlogin oidclogin secrets usage

# This command does not set a exit code if there is no token, so just
# capture the output and check if it's empty later.  It will print the
# token from ~/.vault-token or $VAULT_TOKEN if it exists.
TOKEN := $(shell vault print token)

usage:
	@echo "Usage:"
	@echo "  make oidclogin"
	@echo "  make tokenlogin"
	@echo "  make secrets - make secrets.txt"
	@echo ""
	@echo "VAULT_ADDR must be set.  And if you set VAULT_TOKEN, you don't need to log in."
	@echo ""
	@# This makefile maybe needs a "approlelogin" target too

tokenlogin:
	@if [ -z "$(VAULT_ADDR)" ]; then echo "VAULT_ADDR is not set"; exit 1; fi
	vault login -method=token

oidclogin:
	@if [ -z "$(VAULT_ADDR)" ]; then echo "VAULT_ADDR is not set"; exit 1; fi
	vault login -method=oidc

# Note: the secrets.txt file will not be updated by the
# consul-template engine if there is no change in the secrets since
# last time.  Delete the file to get a fresh timestamp.

secrets:
	@if [ -z "$(VAULT_ADDR)" ]; then echo "VAULT_ADDR is not set"; exit 1; fi;
	@if [ -z "$(TOKEN)" ]; then echo "Please log in or set VAULT_TOKEN first"; exit 1; fi
	@# Avoid echoing the token so it doesn't get logged, but still
	@# show that we're making the secrets.txt file
	@echo Generating secrets.txt
	@consul-template -vault-token="$(TOKEN)" -template="secrets.ctmpl:secrets.txt" -once
	@ls -l secrets.txt
