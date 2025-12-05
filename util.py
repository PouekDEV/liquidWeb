# Gracefully taken from liquidctl

def normalizeProfile(profile, critx, max_value=100):
    profile = sorted(list(profile) + [(critx, max_value)], key=lambda p: (p[0], -p[1]))
    mono = profile[0:1]
    for (x, y), (xb, yb) in zip(profile[1:], profile[:-1]):
        if x == xb:
            continue
        if y < yb:
            y = yb
        mono.append((x, y))
        if y == max_value:
            break
    return mono

def interpolateProfile(profile, x):
    lower, upper = profile[0], profile[-1]
    for step in profile:
        if step[0] <= x:
            lower = step
        if step[0] >= x:
            upper = step
            break
    if lower[0] == upper[0]:
        return lower[1]
    return round(lower[1] + (x - lower[0])/(upper[0] - lower[0])*(upper[1] - lower[1]))

def clamp(value, clampmin, clampmax):
    clamped = max(clampmin, min(clampmax, value))
    return clamped

# ---