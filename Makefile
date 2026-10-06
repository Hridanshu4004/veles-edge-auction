.PHONY: demo test up down seed logs

demo:
	python3 main.py

test:
	pytest -q

up:
	docker compose up --build -d

down:
	docker compose down -v

seed:
	docker compose exec backend python web/backend/seed.py

logs:
	docker compose logs -f
