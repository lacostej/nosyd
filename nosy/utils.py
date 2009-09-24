def findall(seq, f):
    """Return all the element in seq where f(item) == True."""
    result = []
    for element in seq:
      if f(element):
        result.append(element)
    return result
