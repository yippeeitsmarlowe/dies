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

# save.py
import json

SAVE_PATH = "save.json"

DEFAULT_SAVE = {
    "coins": 0,
    "upgrades": {
        "extra_time": 0,
        "score_mult": 0,
        "reroll": 0,
        "color_count_minus": 0,
    }
}

def load_save():
    # ALWAYS reset on boot
    data = DEFAULT_SAVE.copy()
    data["upgrades"] = DEFAULT_SAVE["upgrades"].copy()
    write_save(data)
    return data

def write_save(data):
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

