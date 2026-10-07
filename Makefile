.PHONY: demo test up down seed logs

demo:
	python3 main.py

test:
	pytest -q

up:
	docker compose up --build -d

down:
	docker compose down -v


logs:
	docker compose logs -f

seed:
	SEED=$${SEED:-42} N_NODES=$${N_NODES:-30} N_TASKS=$${N_TASKS:-500} .venv/bin/python scripts/seed.py
