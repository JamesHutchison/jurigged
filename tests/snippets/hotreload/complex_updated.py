PAD = "line anchor"
PAD2 = "line anchor 2"
from functools import wraps


def tag(fn):
    @wraps(fn)
    def wrapped(value):
        return f"v2:{fn(value)}"

    return wrapped


@tag
def pipeline(value):
    base = value + 10

    def middle(multiplier):
        adjusted = base * (multiplier + 1)

        def leaf(offset):
            return adjusted - offset

        return leaf(4)

    return middle(3)
