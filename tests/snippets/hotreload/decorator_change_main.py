def counted(fn):
    def wrapped(value):
        return fn(value) + 1

    return wrapped


@counted
def work(value):
    return value * 2
