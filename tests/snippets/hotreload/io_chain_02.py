TAG = "s1"
DECORATOR_BONUS = 0


def decorate(fn):
    def wrapper(value):
        return f"{TAG}:{fn(value) + DECORATOR_BONUS}"

    return wrapper


def raw_pipeline(value):
    seed = value + 1

    def inner(multiplier):
        return seed * multiplier

    return inner(3)


pipeline = decorate(raw_pipeline)
