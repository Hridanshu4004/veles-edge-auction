import os
import sys
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, repo_root)

from web.backend.models import Base, Node, NodeLink, Task
from common.loaders import WSDreamLoader, Azure2019Loader

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c

def main():
    seed = int(os.environ.get("SEED", 42))
    n_nodes = int(os.environ.get("N_NODES", 30))
    n_tasks = int(os.environ.get("N_TASKS", 500))
    
    rng = np.random.default_rng(seed)
    
    db_path = os.path.join(repo_root, "edgetruth.db")
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    session.query(NodeLink).delete()
    session.query(Node).delete()
    session.query(Task).delete()
    session.commit()
    
    raw_wsdream = os.path.join(repo_root, "data", "raw", "wsdream")
    sample_wsdream = os.path.join(repo_root, "data", "samples", "wsdream")
    ws_dir = raw_wsdream if os.path.exists(raw_wsdream) else sample_wsdream
    
    raw_azure = os.path.join(repo_root, "data", "raw", "azure", "2019")
    sample_azure = os.path.join(repo_root, "data", "samples", "azure")
    az_dir = raw_azure if os.path.exists(raw_azure) else sample_azure
    
    print(f"Using WSDream from: {ws_dir}")
    print(f"Using Azure from: {az_dir}")
    
    try:
        ws_loader = WSDreamLoader(ws_dir, seed=seed)
        ws_data = ws_loader.load_and_split(n_nodes=n_nodes, allow_test=False)
        nodes_df = ws_data["users"].head(n_nodes)
    except Exception as e:
        print(f"Fallback to samples (nodes): {e}")
        nodes_df = pd.read_csv(os.path.join(sample_wsdream, "users_sample.csv")).head(n_nodes)
        
    try:
        az_loader = Azure2019Loader(az_dir, seed=seed)
        az_data = az_loader.load_and_split(allow_test=False)
        tasks_df = az_data["DEV"]["tasks"].head(n_tasks)
    except Exception as e:
        print(f"Fallback to samples (tasks): {e}")
        tasks_df = pd.read_csv(os.path.join(sample_azure, "DEV", "tasks_sample.csv")).head(n_tasks)
    
    db_nodes = []
    for _, row in nodes_df.iterrows():
        lat = float(row.get("Lat", rng.uniform(-90, 90)))
        lon = float(row.get("Lon", rng.uniform(-180, 180)))
        country = str(row.get("Country", "Unknown"))
        ip = str(row.get("IP", "0.0.0.0"))
        uid = str(row.get("UserID", f"node_{rng.integers(1000)}"))
        
        n = Node(
            id=uid,
            name=ip,
            region=country,
            country=country,
            lat=lat,
            lon=lon,
            cost=float(rng.uniform(0.01, 0.5)),
            reliability=float(rng.uniform(0.7, 1.0)),
            capacity_cpu=int(rng.integers(2, 32)),
            capacity_memory=int(rng.integers(1024, 65536)),
            true_latency_ms=float(rng.uniform(10, 100)),
            node_type="WS_DREAM",
            data_source="WSDream"
        )
        db_nodes.append(n)
        session.add(n)
    session.commit()
    
    for i, n1 in enumerate(db_nodes):
        for j, n2 in enumerate(db_nodes):
            if i != j:
                dist = haversine(n1.lat, n1.lon, n2.lat, n2.lon)
                latency = dist * 0.02 + 5.0
                link = NodeLink(
                    source_id=n1.id,
                    target_id=n2.id,
                    latency_ms=latency,
                    data_source="Derived:Distance"
                )
                session.add(link)
    session.commit()
    
    for _, row in tasks_df.iterrows():
        t = Task(
            id=f"{row.get('HashFunction', 'task')}_{uuid.uuid4().hex[:8]}",
            task_value=float(rng.uniform(1.0, 100.0)),
            max_latency_ms=float(row.get("duration_ms", 200.0)),
            required_cpu=int(rng.integers(1, 4)),
            required_memory=int(row.get("memory_mb", 1024)),
            data_source="Azure2019"
        )
        session.add(t)
    session.commit()
    
    print("\n--- TABLE COUNTS ---")
    print("Nodes:", session.query(Node).count())
    print("NodeLinks:", session.query(NodeLink).count())
    print("Tasks:", session.query(Task).count())
    
    print("\n--- SAMPLE NODES ---")
    for x in session.query(Node).limit(5):
        print(f"[{x.data_source}] {x.id} | {x.country} | Lat:{x.lat} Lon:{x.lon} | Cost:{x.cost:.2f} Rel:{x.reliability:.2f}")

    print("\n--- SAMPLE LINKS ---")
    for x in session.query(NodeLink).limit(5):
        print(f"[{x.data_source}] {x.source_id} -> {x.target_id} | {x.latency_ms:.1f}ms")

    print("\n--- SAMPLE TASKS ---")
    for x in session.query(Task).limit(5):
        print(f"[{x.data_source}] {x.id} | Val:{x.task_value:.2f} | MaxLat:{x.max_latency_ms:.1f}ms")

if __name__ == "__main__":
    main()
