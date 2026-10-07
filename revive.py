import httpx, time
B = "http://localhost:8000/api"
for n in httpx.get(f"{B}/nodes").json():
    r = httpx.post(f"{B}/nodes/{n['id']}/heartbeat")
    print("heartbeat", n["id"], r.status_code)
for t in httpx.get(f"{B}/tasks").json():
    if str(t.get("status", "")).upper() == "PENDING":
        r = httpx.post(f"{B}/auctions/run", json={"task_id": t["id"]})
        print("auction", t["id"], r.status_code, r.text[:120])
time.sleep(1)
print(httpx.get(f"{B}/metrics").json())
