decoration_count = 0


def counted(fn):
    global decoration_count
    decoration_count += 1

    def wrapped(value):
        return fn(value) + 1

    return wrapped


@counted
def work(value):
    return value * 5
