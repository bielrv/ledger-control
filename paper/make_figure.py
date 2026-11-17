"""Figure 1: per-transcript suspicion scores by monitor, honest vs attacked, refusals marked."""
import json
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parent.parent
recs = [json.loads(l) for l in open(ROOT / "results/scored.jsonl", encoding="utf-8")]
monitors = [("haiku", "Haiku 5.5"), ("haiku+controls", "Haiku 5.5\n+ controls"), ("opus", "Opus 5.5\nJSON"),
            ("opus+controls", "Opus 5.5 JSON\n+ controls"), ("opus_plain", "Opus 5.5\nplain text")]

fig, ax = plt.subplots(figsize=(3.3, 2.5))
for i, (key, _) in enumerate(monitors):
    for attack, color, dx in ((False, "#2b6cb0", -0.17), (True, "#c53030", 0.17)):
        rs = [r for r in recs if r["attack"] == attack]
        scored = [r["monitor"][key]["suspicion"] for r in rs if r["monitor"][key]["suspicion"] is not None]
        refused = sum(r["monitor"][key]["suspicion"] is None for r in rs)
        xs = [i + dx + ((j % 7) - 3) * 0.022 for j in range(len(scored))]
        ax.scatter(xs, scored, s=7, color=color, alpha=0.75, linewidths=0)
        if refused:
            ax.text(i + dx, 108, f"R{refused}", color=color, ha="center", va="bottom", fontsize=6, fontweight="bold")
ax.axhline(50, color="0.6", lw=0.6, ls="--")
ax.set_xticks(range(len(monitors)))
ax.set_xticklabels([m[1] for m in monitors], fontsize=5.5)
ax.set_ylim(-5, 122)
ax.set_yticks([0, 25, 50, 75, 100])
ax.tick_params(axis="y", labelsize=6)
ax.set_ylabel("Suspicion score", fontsize=7)
ax.scatter([], [], s=7, color="#2b6cb0", label="honest (n=15)")
ax.scatter([], [], s=7, color="#c53030", label="attacked (n=30)")
ax.legend(fontsize=5.5, loc="center left", frameon=False, bbox_to_anchor=(0.0, 0.55))
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout(pad=0.3)
fig.savefig(pathlib.Path(__file__).with_name("fig_scores.pdf"))
