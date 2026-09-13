def _parse(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in version.strip().split("."))


def is_compatible(requirement: str | None, current_version: str) -> bool:
    """Supports the simple ">=1.0.0" style requirement strings from the
    module manifest (section 23). An unrecognized format doesn't block
    the install - better to let a human notice a weird version string
    than to silently brick installs over a format this can't parse."""
    if not requirement:
        return True

    requirement = requirement.strip()
    for op, length in ((">=", 2), ("<=", 2), ("==", 2), (">", 1), ("<", 1)):
        if requirement.startswith(op):
            try:
                required = _parse(requirement[length:])
                current = _parse(current_version)
            except ValueError:
                return True
            if op == ">=":
                return current >= required
            if op == "<=":
                return current <= required
            if op == "==":
                return current == required
            if op == ">":
                return current > required
            return current < required
    return True
