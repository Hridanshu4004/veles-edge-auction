import httpx
res = httpx.post("http://localhost:8000/api/auctions/run", json={"task_id": "task-1"})
print(res.status_code)
print(res.json())
