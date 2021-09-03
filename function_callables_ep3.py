# def hypervolume(*args):
#     print(args)
#     print(type(args))

# hypervolume(2, 3, 4)  

def hypervolume(*lengths):
    i = iter(lengths)
    v = next(i)
    for length in i:
        v *= length
    return v

print(hypervolume(1))

def hypervolume(length, *lengths):
    v = length
    for item in lengths:
        v *= item
    return v

print(hypervolume(3, 5, 7, 9))


def tag(name, **kwargs):
    print(name)
    print(kwargs)
    print(type(kwargs))

print(tag('img', src="Monet.jpg", alt="Sunrise by Claude Monet", border=1))


def tag(name, **attributes):
    result = '<' + name
    for key, value in attributes.items():
        result += ' {k}="{v}"'.format(k=key, v=str(value))
    result += '>'
    return result

print(tag('img', src="Monet.jpg", alt="Sunrise by Claude Monet", border=1))