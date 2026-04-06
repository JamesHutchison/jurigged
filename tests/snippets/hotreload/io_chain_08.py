# shift line map 1
# shift line map 2
# shift line map 3
TAG = "s8"
DECORATOR_BONUS = 1


def decorate(fn):
    def wrapper(value):
        return f"{TAG}:{fn(value) + DECORATOR_BONUS}"

    return wrapper


def raw_pipeline(value):
    seed = value + 2

    def inner(multiplier):
        def leaf(offset):
            return seed * multiplier + offset

        return leaf(2)

    return inner(3)


pipeline = decorate(raw_pipeline)
