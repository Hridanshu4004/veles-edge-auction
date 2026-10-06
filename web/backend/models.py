from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from .database import Base

class Node(Base):
    __tablename__ = "nodes"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    region = Column(String, default="default")
    country = Column(String)
    lat = Column(Float)
    lon = Column(Float)
    cost = Column(Float)
    reliability = Column(Float)
    capacity_cpu = Column(Integer)
    capacity_memory = Column(Integer)
    true_latency_ms = Column(Float)
    node_type = Column(String)
    capabilities = Column(JSON, default=list)
    status = Column(String, default="ONLINE")
    data_source = Column(String)
    last_heartbeat = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class NodeLink(Base):
    __tablename__ = "node_links"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    source_id = Column(String, ForeignKey("nodes.id"))
    target_id = Column(String, ForeignKey("nodes.id"))
    latency_ms = Column(Float)
    data_source = Column(String)

class NodeObservation(Base):
    __tablename__ = "node_observations"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    node_id = Column(String, ForeignKey("nodes.id"))
    task_id = Column(String, ForeignKey("tasks.id"))
    success = Column(Boolean)
    latency_ms = Column(Float)
    observed_at = Column(DateTime(timezone=True), server_default=func.now())

class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True, index=True)
    task_value = Column(Float)
    max_latency_ms = Column(Float)
    required_cpu = Column(Integer)
    required_memory = Column(Integer)
    status = Column(String, default="PENDING")
    data_source = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Allocation(Base):
    __tablename__ = "allocations"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    node_id = Column(String, ForeignKey("nodes.id"))
    score = Column(Float)
    price = Column(Float)
    success_probability = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Execution(Base):
    __tablename__ = "executions"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    node_id = Column(String, ForeignKey("nodes.id"))
    success = Column(Boolean)
    latency_ms = Column(Float)
    payment = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
