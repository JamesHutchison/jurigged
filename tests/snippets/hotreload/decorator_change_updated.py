def counted(fn):
    def wrapped(value):
        return fn(value) + 3

    return wrapped


@counted
def work(value):
    return value * 2
