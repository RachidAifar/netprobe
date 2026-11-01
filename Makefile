.PHONY: help install test lint up down elk validate cluster destroy

help:  ## Show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

install:  ## Install the app and dev tools into .venv
	python3 -m venv .venv && .venv/bin/pip install -e "app[dev]" yamllint ansible-lint

test:  ## Run unit tests with coverage
	cd app && ../.venv/bin/pytest --cov=netprobe --cov-report=term-missing

lint:  ## Lint Python, YAML and Ansible
	cd app && ../.venv/bin/ruff check . && ../.venv/bin/ruff format --check .
	.venv/bin/yamllint -s .
	.venv/bin/ansible-lint infra/ansible

up:  ## Start NetProbe + Prometheus + Grafana with Docker Compose
	docker compose up -d --build

elk:  ## Start the stack plus Elasticsearch, Kibana and Filebeat
	docker compose -f compose.yaml -f compose.elk.yaml up -d --build

down:  ## Stop all containers
	docker compose -f compose.yaml -f compose.elk.yaml down

validate:  ## Validate Kubernetes manifests and Terraform
	for o in deploy/k8s/overlays/*/; do kubectl kustomize $$o | kubeconform -strict -summary -ignore-missing-schemas; done
	cd infra/terraform && terraform fmt -check && terraform init -backend=false -input=false >/dev/null && terraform validate

cluster:  ## Create the kind cluster with Argo CD and monitoring (GitOps)
	cd infra/terraform && terraform init -input=false && terraform apply

destroy:  ## Delete the kind cluster
	cd infra/terraform && terraform destroy
