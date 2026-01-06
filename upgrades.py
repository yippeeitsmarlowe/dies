# upgrades.py
from dataclasses import dataclass

@dataclass
class UpgradeDef:
    key: str
    name: str
    desc: str
    base_cost: int
    cost_scale: float
    max_level: int

UPGRADE_DEFS = [
    UpgradeDef("extra_time", "Extra Time", "+10 seconds per level", base_cost=10, cost_scale=1.55, max_level=10),
    UpgradeDef("score_mult", "Score Mult", "+10% score per level", base_cost=12, cost_scale=1.6, max_level=10),
    UpgradeDef("reroll", "Reroll", "Gain +1 reroll per run", base_cost=15, cost_scale=1.8, max_level=5),
    UpgradeDef("color_count_minus", "Fewer Colors", "Reduce color types by 1 (easier)", base_cost=25, cost_scale=2.0, max_level=2),
]

def upgrade_cost(defn: UpgradeDef, level: int) -> int:
    # cost to buy NEXT level (level is current)
    return int(defn.base_cost * (defn.cost_scale ** level))

def can_buy(save_data, defn: UpgradeDef) -> bool:
    lvl = int(save_data["upgrades"].get(defn.key, 0))
    if lvl >= defn.max_level:
        return False
    return save_data["coins"] >= upgrade_cost(defn, lvl)

def buy_upgrade(save_data, defn: UpgradeDef) -> bool:
    if not can_buy(save_data, defn):
        return False
    lvl = int(save_data["upgrades"].get(defn.key, 0))
    cost = upgrade_cost(defn, lvl)
    save_data["coins"] -= cost
    save_data["upgrades"][defn.key] = lvl + 1
    return True

def apply_run_modifiers(settings_obj, upgrades_dict):
    # returns (time_seconds, score_multiplier, colors_count, rerolls)
    extra_time = upgrades_dict.get("extra_time", 0) * 10
    score_mult = 1.0 + upgrades_dict.get("score_mult", 0) * 0.10
    color_minus = upgrades_dict.get("color_count_minus", 0)
    colors = max(3, settings_obj.BASE_COLORS - color_minus)
    rerolls = upgrades_dict.get("reroll", 0)
    time_seconds = settings_obj.BASE_TIME_SECONDS + extra_time
    return time_seconds, score_mult, colors, rerolls
