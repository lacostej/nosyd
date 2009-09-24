import nosy

class TestNosy:

  def setUp(self):
    print "setUp"
    self.n = nosy.Nosy()

  def tearDown(self):
    self.n = None

  def test_xxx(self):
    print self.n
    assert True 
