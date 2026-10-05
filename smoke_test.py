import json
import urllib.error
import urllib.request


def test_registry():
    base_url = "http://localhost:8001"
    
    print("Testing Registry Health...")
    try:
        with urllib.request.urlopen(f"{base_url}/health") as response:
            status = response.getcode()
            body = response.read().decode('utf-8')
            print(f"Health Response: {status} {body}")
    except Exception as e:  # noqa: BLE001
        print(f"Health check failed: {e}")

    print("\nRegistering a Node...")
    payload = json.dumps({"id": "node-1", "capacity": {"cpu": 4, "ram": 8}}).encode('utf-8')
    req = urllib.request.Request(f"{base_url}/register", data=payload, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            body = response.read().decode('utf-8')
            print(f"Register Response: {status} {body}")
    except Exception as e:  # noqa: BLE001
        print(f"Register failed: {e}")

    print("\nGetting Nodes...")
    try:
        with urllib.request.urlopen(f"{base_url}/nodes") as response:
            status = response.getcode()
            body = response.read().decode('utf-8')
            print(f"Nodes Response: {status} {body}")
    except Exception as e:  # noqa: BLE001
        print(f"Get nodes failed: {e}")

    print("\nTesting Auctioneer Health...")
    try:
        with urllib.request.urlopen("http://localhost:8002/health") as response:
            status = response.getcode()
            body = response.read().decode('utf-8')
            print(f"Auctioneer Health Response: {status} {body}")
    except Exception as e:  # noqa: BLE001
        print(f"Auctioneer health check failed: {e}")

if __name__ == "__main__":
    import time
    time.sleep(2) # wait for servers to fully start
    test_registry()
