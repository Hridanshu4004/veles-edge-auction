from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

from pydantic import BaseModel
class Node(BaseModel):
    id: str
    capacity: dict
nodes = []
@app.post("/register")
def register(node: Node):
    nodes.append(node)
    return {"status": "registered"}
@app.get("/nodes")
def get_nodes():
    return nodes
