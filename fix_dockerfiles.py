import pathlib

base_dir = pathlib.Path("/home/hridanshu/veles-edge-auction")

for s in ["registry", "auctioneer", "node_agent", "task_gen"]:
    df_path = base_dir / f"services/{s}/Dockerfile"
    content = df_path.read_text()
    if content.endswith("\\n"):
        content = content[:-2] + "\n"
        df_path.write_text(content)
