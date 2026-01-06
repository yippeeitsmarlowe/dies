# utils.py
import random

def clamp(n, a, b):
    return max(a, min(b, n))

def rand_choice_excluding(options, excluded):
    pool = [o for o in options if o != excluded]
    return random.choice(pool) if pool else random.choice(options)

def lerp(a, b, t):
    return a + (b - a) * t
