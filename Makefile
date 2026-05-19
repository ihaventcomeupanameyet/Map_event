.PHONY: help prod-build prod-up prod-down prod-restart prod-logs prod-ps prod-refresh prod-pull

COMPOSE_PROD = docker compose -f docker-compose.production.yml

help:
	@printf '%s\n' \
		'make prod-build   Build the production images' \
		'make prod-up      Start the production stack with a rebuild' \
		'make prod-down    Stop the production stack' \
		'make prod-restart Recreate the production stack with a rebuild' \
		'make prod-logs    Tail production logs' \
		'make prod-ps      Show production container status' \
		'make prod-refresh Trigger the backend refresh job' \
		'make prod-pull    Pull production images when image refs are configured'

prod-build:
	$(COMPOSE_PROD) build

prod-up:
	$(COMPOSE_PROD) up -d --build --remove-orphans

prod-down:
	$(COMPOSE_PROD) down

prod-restart: prod-down prod-up

prod-logs:
	$(COMPOSE_PROD) logs -f --tail=200

prod-ps:
	$(COMPOSE_PROD) ps

prod-refresh:
	curl -fsS -X POST http://localhost:8000/jobs/refresh-events

prod-pull:
	$(COMPOSE_PROD) pull
