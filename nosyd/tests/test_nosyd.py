import nosyd

class TestNosyd:

  def setUp(self):
    self.n = nosyd.NosyProject()

  def tearDown(self):
    self.n = None

  def test_parse_xunit_results(self):
    r = nosyd.parse_xunit_results("tests/data/nosetests_1.xml")
    print r
    assert r.errors == 0
    assert r.failures == 1
    assert len(r.testcases) == 1
    assert r.testcases[0].failed() == True
    assert r.testcases[0].failure.type == "exceptions.AssertionError"

    assert len(r.list_failure_names()) == 1
    assert r.list_failure_names()[0] == "tests.test_nosy.TestNosy.test_xxx"

  def test_parse_non_existing_file(self):
    r = nosyd.parse_xunit_results("tests/data/IDONTEXIST.xml")
    assert r == None

  def test_parse_surefire_results(self):
    r = nosyd.parse_surefire_results("tests/data/surefire_report_1.xml")
    print r
    assert r.errors == 0
    assert r.failures == 0
    assert r.skip == 0
    assert len(r.testcases) == 7

  def test_add_results(self):
    r1 = nosyd.parse_xunit_results("tests/data/nosetests_1.xml")
    r2 = nosyd.parse_surefire_results("tests/data/surefire_report_1.xml")
    r = r1 + r2
    assert r.errors == 0
    assert r.failures == 1
    assert r.skip == 0
    assert len(r.testcases) == 8

  def test_FileSet_build_re_pattern(self):
    re_pattern = nosyd.FileSet(".", "ignored").build_pattern("src/main/java/**/com/*.java")
    assert re_pattern == "src/main/java/.*/com/[^/]*.java$"


