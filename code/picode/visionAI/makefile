.EXPORT_ALL_VARIABLES:

VENV_DIR=backend/venv
VENV_PIP=$(VENV_DIR)/bin/pip
VENV_UVICORN=$(VENV_DIR)/bin/uvicorn

# Install dependencies
install:
	python3 -m venv $(VENV_DIR)
	$(VENV_PIP) install -r backend/requirements.txt
	cd frontend && npm install

build_frontend:
	cd frontend && npm install && npm run build

# Run the application in development mode
run_backend:
	cd backend && ../$(VENV_UVICORN) websrv:app --reload --host 0.0.0.0 --port 3000

run_frontend:
	cd frontend && npm run serve

run:
	make run_backend & make run_frontend

start:
	make run

run_pi_backend:
	cd backend && PYTHONPYCACHEPREFIX=/tmp/pycache ../$(VENV_UVICORN) websrv:app --host 0.0.0.0 --port 3000

# Testing
install_test:
	pip3 install coverage pytest pytest-cov

test:
	cd backend && pytest --cov-report term --cov=. --cov-report=html -sx

# Code quality
format:
	# -----  Formatting Python code with Black
	cd backend && black .

	# -----  Formatting JavaScript code with Prettier
	cd frontend && npm run prettier

check:
	# -----  Validating Black code style
	cd backend && black --check --diff .

	# -----  Validating Flake8 code style
	cd backend && flake8 .

	# -----  Validating Prettier code style
	cd frontend && npm run prettier:check

	# -----  Validating CSpell errors
	cspell --no-progress .

	# ----- The code is formatted correctly
