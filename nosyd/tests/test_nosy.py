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
    assert len(r.testcases) == 1
    assert r.testcases[0].failed() == True
    assert r.testcases[0].failure.type == "exceptions.AssertionError"

    assert len(r.list_failure_names()) == 1
    assert r.list_failure_names()[0] == "tests.test_nosy.TestNosy.test_xxx"

  def test_parse_non_existing_file(self):
    r = nosy.parse_xunit_results("tests/data/IDONTEXIST.xml")
    assert r == None
