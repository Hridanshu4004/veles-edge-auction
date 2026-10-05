import json
import os


def test_scenarios_exist():
    assert os.path.exists("scenarios/clean.json")
    assert os.path.exists("scenarios/liars.json")
    assert os.path.exists("scenarios/mixed_adversary.json")
    
def test_scenario_format():
    with open("scenarios/clean.json", "r") as f:
        data = json.load(f)
    assert data["scenario_name"] == "CLEAN_MARKET"
    assert "nodes" in data
    assert "tasks" in data
    assert "network" in data
    assert "ground_truth" in data
    assert len(data["nodes"]) == 10
    assert len(data["tasks"]) == 50
