.PHONY: test coverage install-dev

install-dev:
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v

coverage:
	pytest tests/ --cov=src/planka_tools --cov-report=term-missing --cov-report=html:htmlcov
