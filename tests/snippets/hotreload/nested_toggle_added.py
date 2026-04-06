def compose(value):
    def inner():
        def extra():
            return value * 2

        return extra() + 1

    return inner()
