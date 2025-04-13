def outer(a):
    b = a + 1

    def inner(c):
        d = c * b
        return d

    return inner(a)
