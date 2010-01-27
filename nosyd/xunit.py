import logging

logger = logging.getLogger("nosyd")

class XunitTestSuite:
  def __init__(self, name, tests, errors, failures, skip, testcases):
    self.name = name
    self.tests = tests
    self.errors = errors
    self.failures = failures
    self.skip = skip
    self.testcases = testcases

  def __add__(self, o):
    return XunitTestSuite("combined", self.tests + o.tests, self.errors + o.errors, self.failures + o.failures, self.skip + o.skip, self.testcases + o.testcases)

  def __str__(self):
    return "XunitTestSuite: %s %s %s %s %s" % (self.name , self.tests, self.errors, self.failures, self.skip)

  def failed_testcase(self, tc):
    return tc.failed()

  def list_failure_names(self):
    failed_testcases = filter(self.failed_testcase, self.testcases)
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

def parse_xunit_results(filename, skip_attr_name='skip'):
  try :
    from xml.dom import minidom
    xmldoc = minidom.parse(filename)
    return parse_xunit_tsuite(xmldoc.firstChild, skip_attr_name)
  except Exception, e:
    logger.error("Couldn't parse file " + filename + ": " + str(type(e)) + " " + str(e))
    return None

def parse_surefire_results(filename):
  return parse_xunit_results(filename, 'skipped')

def parse_gradle_suites_results(filename):
  try :
    from xml.dom import minidom
    xmldoc = minidom.parse(filename)
    tsuites = xmldoc.firstChild.getElementsByTagName('testsuite')
    result = None
    for ts in tsuites:
      new = parse_xunit_tsuite(ts, None)
      if result is None:
        result = new
      else:
        result += new
    return result
  except Exception, e:
    logger.error("Couldn't parse file " + filename + ": " + str(type(e)) + " " + str(e))
    import traceback
    logger.error(traceback.format_exc(e))
    return None

def parse_xunit_tsuite(ts, skip_attr_name='skip'):
  tcs = ts.getElementsByTagName('testcase')
  testcases = []
  for tc in tcs:
    failure = None
    failureNode = None
    failures = tc.getElementsByTagName('failure')
    if len(failures) > 0:
      failureNode = failures[0]
    errors = tc.getElementsByTagName('error')
    if len(errors) > 0:
      failureNode = errors[0]
    if failureNode != None:
      failure = Failure(attr_val(failureNode, 'type'), failureNode.childNodes[0].data)
    testcases.append(TestCase(attr_val(tc, 'classname'), attr_val(tc, 'name'), failure))
  skipped = 0
  if skip_attr_name != None:
    skipped = int(attr_val(ts, skip_attr_name))
  return XunitTestSuite(attr_val(ts, 'name'), int(attr_val(ts, 'tests')), int(attr_val(ts, 'errors')), int(attr_val(ts, 'failures')), skipped, testcases)

def attr_val(node, attr_name):
  if node is None:
    raise Exception("None node");
  if node.attributes is None:
    raise Exception("None node.attributes "  + str(type(node)));
  return node.attributes[attr_name].value

