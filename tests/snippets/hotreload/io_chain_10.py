# final line shift 1
# final line shift 2
# final line shift 3
# final line shift 4
TAG = "final"
DECORATOR_BONUS = 7


def decorate(fn):
    def wrapper(value):
        return f"{TAG}:{fn(value) + DECORATOR_BONUS}"

    return wrapper


def raw_pipeline(value):
    seed = value + 5

    def inner(multiplier):
        def leaf(offset):
            return seed * multiplier + offset

        return leaf(3)

    return inner(2)


pipeline = decorate(raw_pipeline)
