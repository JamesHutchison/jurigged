PREFIX = "a"
PREFIX2 = "b"


def keep_line_numbers_stable():
    base = 10

    def inner():
        value = base + 3
        return value

    return inner()
