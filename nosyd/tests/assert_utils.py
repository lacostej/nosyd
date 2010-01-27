def assertEquals(a, b):
  result = (a == b)
  if (not result):
    print str(a) + " not equals to\n" + str(b)
    assert False

def assertNotEquals(a, b):
  result = (a != b)
  if (not result):
    print str(a) + " equals to\n" + str(b)
    assert False
