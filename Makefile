up:
	docker compose up -d
down:
	docker compose down
test:
	pytest
bench:
	echo "Benchmarking..."
lint:
	ruff check .
logs:
	docker compose logs -f
