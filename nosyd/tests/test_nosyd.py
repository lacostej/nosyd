from nosyd.nosyd import *

class TestNosyd:

  def setUp(self):
    self.n = NosyProject()

  def tearDown(self):
    self.n = None

  def test_parse_xunit_results(self):
    r = parse_xunit_results("tests/data/nosetests_1.xml")
    print r
    assert r.errors == 0
    assert r.failures == 1
    assert len(r.testcases) == 1
    assert r.testcases[0].failed() == True
    assert r.testcases[0].failure.type == "exceptions.AssertionError"

    assert len(r.list_failure_names()) == 1
    assert r.list_failure_names()[0] == "tests.test_nosy.TestNosy.test_xxx"

  def test_parse_non_existing_file(self):
    r = parse_xunit_results("tests/data/IDONTEXIST.xml")
    assert r == None

  def test_parse_surefire_results(self):
    r = parse_surefire_results("tests/data/surefire_report_1.xml")
    print r
    assert r.errors == 0
    assert r.failures == 0
    assert r.skip == 0
    assert len(r.testcases) == 7

  def test_add_results(self):
    r1 = parse_xunit_results("tests/data/nosetests_1.xml")
    r2 = parse_surefire_results("tests/data/surefire_report_1.xml")
    r = r1 + r2
    assert r.errors == 0
    assert r.failures == 1
    assert r.skip == 0
    assert len(r.testcases) == 8

  def test_FileSet_build_re_pattern(self):
    re_pattern = FileSet(".", "ignored")._to_re_build_pattern("src/main/java/**/com/*.java")
    print re_pattern
    assert re_pattern == "src/main/java/.*/com/[^/]*.java$"


