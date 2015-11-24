i = 40

class Inc(object):
    def __init__(self, integ):
        self.integer = integ

    def foo(self):
        self.integer[0] += 1

print(i)
obj = Inc([i])
obj.foo()
print(i)