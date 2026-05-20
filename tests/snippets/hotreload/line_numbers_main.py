def keep_line_numbers_stable():
    base = 10

    def inner():
        return base + 1

    return inner()
