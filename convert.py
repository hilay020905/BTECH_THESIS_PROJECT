import json
import matplotlib.pyplot as plt

with open("results.json", "r") as f:
    data = json.load(f)

for name, result in data.items():
    history = result["history"]

    plt.figure(figsize=(10, 6))
    plt.plot(range(len(history)), history, marker="o")

    plt.title(name)
    plt.xlabel("Iteration")
    plt.ylabel("Gate Count")
    plt.grid(True)

    plt.savefig(name + ".png", dpi=300, bbox_inches="tight")
    plt.close()

print("PNG graphs created successfully!")