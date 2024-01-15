.PHONEY: container run standalone shell default

default:
	@echo
	@echo Use one of these targets:
	@echo
	@echo "  container  - build a container just like jenkins does"
	@echo "  standalone - after making \"container\" you can make standalone, this"
	@echo "               makes the container look more like it will in kubernetes"
	@echo "               and copies _db.php to provide a database configuration that"
	@echo "               does not rely on secrets from vault"
	@echo "  run        - Run the container with redirect from 8080 on localhost to"
	@echo "               apache inside.  You probably want to make \"standalone\" first"
	@echo "  shell      - Start a shell in the container to inspect it"
	@echo


container:
	docker build -t docker-registry-checker .

run: container
	docker container run -p 8080:80 --rm -it docker-registry-checker:latest

# Build container (jenkins like) or standalone (looks like kubernetes
# env, isn't) first
shell:	container
	docker container run --rm -it docker-registry-checker:latest /bin/bash
