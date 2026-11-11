"""ContraDoc's gate power, paired accuracy, normal approximation (GATE_SET.md section 5). No data read.

Usage: contradoc_power.py   prints the sizes needed and the powers at the largest set role B can draw.
"""
from statistics import NormalDist

N = NormalDist()
DELTA = 0.10          # bar (a): the system 10 points above B1 (D-S92, Seckin's)
MARGIN = 0.05         # bar (b): at most 5 points below the cloud reference
POWER = 0.80


def z(level):
    return N.inv_cdf(1 - (1 - level) / 2)


def se(d, delta, n):
    return ((d - delta ** 2) / n) ** 0.5


def needed(d, level, delta=DELTA, power=POWER):
    """Documents for the interval's low end above zero at `level` with `power` at a true `delta`."""
    import math
    return math.ceil((z(level) + N.inv_cdf(power)) ** 2 * (d - delta ** 2) / delta ** 2)


def bar_a(n, d, true, level):
    """(interval alone, joint as coded: point at least .10 and low end above zero) at a true difference."""
    s = se(d, true, n)
    interval = 1 - N.cdf(z(level) - true / s)
    joint = 1 - N.cdf((max(DELTA, z(level) * s) - true) / s)
    return interval, joint


def bar_b(n, d, level, true=0.0):
    """(as coded: the point at least -.05; read on the interval: its low end above -.05) at a true difference."""
    s = (d / n) ** 0.5
    point = 1 - N.cdf((-MARGIN - true) / s)
    interval = 1 - N.cdf(z(level) - (MARGIN + true) / s)
    return point, interval


if __name__ == "__main__":
    for level in (0.95, 0.975):
        print("level %.3f: documents needed (interval alone, power .80): d .20 %d, d .27 %d, d .30 %d"
              % (level, needed(.20, level), needed(.27, level), needed(.30, level)))
    for n in (230, 276, 439):
        for d in (.27, .30):
            for true in (.10, .15):
                i, j = bar_a(n, d, true, .975)
                print("n %d d %.2f true %.2f level .975: interval %.2f joint %.2f" % (n, d, true, i, j))
        for level in (0.90, 0.95, 0.975):
            p, i = bar_b(n, .25, level)
            print("n %d bar (b) d .25 true 0 level %.3f: as coded %.2f, on the interval %.2f" % (n, level, p, i))
