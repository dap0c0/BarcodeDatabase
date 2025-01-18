def foo(var_a, var_b, var_c):
    print(foo.__code__.co_varnames)
    print(foo.__code__.co_varnames.__class__)
    print(locals())

foo("a", "b", "c")
