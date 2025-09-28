# services/fares.py
from datetime import time, datetime

PEAK1 = (time(8, 0), time(10, 0))
PEAK2 = (time(17, 0), time(20, 0))

def is_peak(t=None):
    t = t or datetime.now().time()
    return (PEAK1[0] <= t <= PEAK1[1]) or (PEAK2[0] <= t <= PEAK2[1])

def calc_fare(base: float, seats: int, t=None):
    # base per-seat fare × seats × peak multiplier
    m = 1.2 if is_peak(t) else 1.0
    return round(float(base) * max(1, int(seats)) * m, 2)
