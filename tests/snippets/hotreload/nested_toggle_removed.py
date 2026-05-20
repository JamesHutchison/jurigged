def compose(value):
    def inner():
        return value - 1

    return inner()
