from utils import *

class XunitTestSuite:
  def __init__(self, name, tests, errors, failures, skip, testcases):
    self.name = name
    self.tests = tests
    self.errors = errors
    self.failures = failures
    self.skip = skip
    self.testcases = testcases

  def __str__(self):
    return "XunitTestSuite: %s %s %s %s %s" % (self.name , self.tests, self.errors, self.failures, self.skip)

  def list_failure_names(self):
    failed_testcases = findall(self.testcases, lambda tc : tc.failed())
    return [ el.name for el in failed_testcases ]

class TestCase:
  def __init__(self, classname, name, failure):
    self.classname = classname
    self.name = name
    self.failure = failure

  def failed(self):
    return self.failure != None

class Failure:
  def __init__(self, type, text):
    self.type = type
    self.text = text

def parse_xunit_results(filename):
  try :
    from xml.dom import minidom
    xmldoc = minidom.parse(filename)
    testsuite = xmldoc.firstChild
    tcs = testsuite.getElementsByTagName('testcase')
    testcases = []
    for tc in tcs:
      failure = None
      if (len(tc.childNodes) > 0):
        failureNode = tc.childNodes[0]
        failure = Failure(failureNode.attributes['type'].value, failureNode.childNodes[0].data)
      testcases.append(TestCase(tc.attributes['classname'].value, tc.attributes['name'].value, failure))
    return XunitTestSuite(testsuite.attributes['name'].value, int(testsuite.attributes['tests'].value), int(testsuite.attributes['errors'].value), int(testsuite.attributes['failures'].value), int(testsuite.attributes['skip'].value), testcases)  
  except IOError:
    return None

