.PHONY: help generate_restaurant_descriptions login-ecr deploy jupyter-up jupyter-restart deploy-v1 deploy-v2 destroy-all generate-data generate-data-v2

help: # Show help for each of the Makefile recipes.
	@grep -E '^[a-zA-Z0-9 -]+:.*#'  Makefile | sort | while read -r l; do printf "\033[1;32m$$(echo $$l | cut -f 1 -d':')\033[00m:$$(echo $$l | cut -f 2- -d'#')\n"; done

generate-data: # Generate all data
	python scripts/generate_restaurant_descriptions.py --output-directory ./data/restaurants/

generate-data-v2: # Generate all data V2
	python scripts/generate_restaurant_descriptions_v2.py --output-directory ./data/restaurants-v2/

login-ecr: # Need to login to ECR before doing cdk deploy
	aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws


jupyter-up: # Spins up the jupyter server
	docker-compose -f ./docker/jupyter/compose.yaml build
	docker-compose -f ./docker/jupyter/compose.yaml up -d
	sleep 5
	docker-compose -f ./docker/jupyter/compose.yaml logs | grep 127.0.0.1 | grep token=

jupyter-down: # Stops the jupyter server
	docker-compose -f ./docker/jupyter/compose.yaml down

jupyter-restart: jupyter-down jupyter-up # Restart the jupyter server

deploy-v1: # Deploy V1 stack
	cdk deploy --require-approval never bedrock-agents-cdk-restaurant-reservations-agent

deploy-v2: # Deploy V2 stack
	cdk deploy --require-approval never bedrock-agents-cdk-restaurant-reservations-agent-v2

destroy-all: # Destroy all stacks
	cdk destroy --force --all