# shift line map 1
# shift line map 2
# shift line map 3
TAG = "s4"
DECORATOR_BONUS = 5


def decorate(fn):
    def wrapper(value):
        return f"{TAG}:{fn(value) + DECORATOR_BONUS}"

    return wrapper


def raw_pipeline(value):
    seed = value + 2

    def inner(multiplier):
        return seed * multiplier

    return inner(3)


pipeline = decorate(raw_pipeline)
