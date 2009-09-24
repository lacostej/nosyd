import nosy

class TestNosy:

  def setUp(self):
    self.n = nosy.Nosy()

  def tearDown(self):
    self.n = None

  def test_parse_xunit_results(self):
    r = nosy.parse_xunit_results("tests/data/nosetests_1.xml")
    print r
    assert r.errors == 0
    assert r.failures == 1

  def test_parse_non_existing_file(self):
    r = nosy.parse_xunit_results("tests/data/IDONTEXIST.xml")
    assert r == None
