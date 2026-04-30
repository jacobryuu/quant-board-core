.PHONY: dev test

dev:
	poetry run uvicorn app.main:app --reload

test:
	poetry run pytest
