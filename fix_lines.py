with open("src/nexus_agent/memory/vector_embedding.py", "r") as f:
    content = f.read()

# Fix line 72
content = content.replace("self._model_dir = Path(model_dir) if model_dir else Path.home() / \".nexus-agent\" / \"models\" / \"embeddings\"",
                          "self._model_dir = Path(model_dir) if model_dir else \\\n            Path.home() / \".nexus-agent\" / \"models\" / \"embeddings\"")

# Fix line 200
content = content.replace("token_type_ids = np.array([tokens.get(\"token_type_ids\", [0] * len(tokens[\"input_ids\"]))], dtype=np.int64)",
                          "token_type_ids = np.array(\n                [tokens.get(\"token_type_ids\", [0] * len(tokens[\"input_ids\"]))],\n                dtype=np.int64\n            )")

with open("src/nexus_agent/memory/vector_embedding.py", "w") as f:
    f.write(content)
