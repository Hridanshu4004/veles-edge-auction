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

experiment:
	docker compose exec -e PYTHONPATH=/app registry python experiments/runner.py

report:
	docker compose exec -e PYTHONPATH=/app registry python experiments/analyze.py

demo: experiment report
	docker compose exec -e PYTHONPATH=/app registry python dashboard_gen.py
	@echo "Demo ready! Open dashboard.html in your browser."

ui:
	docker compose up -d dashboard
	@echo "Dashboard ready at http://localhost:8080"
