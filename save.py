# save.py
import json
import os

SAVE_PATH = "save.json"

DEFAULT_SAVE = {
    "coins": 0,
    "upgrades": {
        "extra_time": 0,     # +10s each level
        "score_mult": 0,     # +10% each level
        "reroll": 0,         # rerolls per run
        "color_count_minus": 0,  # reduces colors by 1 (easier) up to 2
    }
}

def load_save():
    if not os.path.exists(SAVE_PATH):
        return DEFAULT_SAVE.copy()
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # fill missing keys
        merged = DEFAULT_SAVE.copy()
        merged.update({k: data.get(k, merged[k]) for k in merged.keys()})
        merged["upgrades"] = DEFAULT_SAVE["upgrades"].copy()
        merged["upgrades"].update(data.get("upgrades", {}))
        return merged
    except Exception:
        return DEFAULT_SAVE.copy()

def write_save(data):
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
