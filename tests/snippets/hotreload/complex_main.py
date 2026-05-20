from functools import wraps


def tag(fn):
    @wraps(fn)
    def wrapped(value):
        return f"v1:{fn(value)}"

    return wrapped


@tag
def pipeline(value):
    base = value + 1

    def middle(multiplier):
        adjusted = base * multiplier

        def leaf(offset):
            return adjusted + offset

        return leaf(3)

    return middle(2)
