#!/usr/bin/env python
# Initial idea from Jeff Winkler, http://jeffwinkler.net
# By Jerome Lacoste, jerome@coffeebreaks.org
# MIT license

import glob,os,stat,time,os.path
import pynotify
import logging

class NosydException(Exception):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return repr(self.value)

'''
An a-la ant FileSet class that allows to identify groups of files that matches patterns. Supports recursivity
'''
class FileSet:
  def __init__(self, dir, pattern):
    self.dir = dir
    self.pattern = pattern

  def find_paths(self):
    # FIXME implement recursivity
    return glob.glob(self.dir + "/" + self.pattern)


############################################################################
# inline the imports until I find out how to properly package a python app #
############################################################################
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
    ts = xmldoc.firstChild
    tcs = ts.getElementsByTagName('testcase')
    testcases = []
    for tc in tcs:
      failure = None
      if (len(tc.childNodes) > 0):
        failureNode = tc.childNodes[0]
        failure = Failure(attr_val(failureNode, 'type'), failureNode.childNodes[0].data)
      testcases.append(TestCase(attr_val(tc, 'classname'), attr_val(tc, 'name'), failure))
    return XunitTestSuite(attr_val(ts, 'name'), int(attr_val(ts, 'tests')), int(attr_val(ts, 'errors')), int(attr_val(ts, 'failures')), int(attr_val(ts, skip_attr_name)), testcases)
  except Exception, e:
    logger.debug("Couldn't parse file " + filename + ": " + str(type(e)) + " " + str(e))
    return None

def parse_surefire_results(filename):
  return parse_xunit_results(filename, 'skipped')

def attr_val(node, attr_name):
  return node.attributes[attr_name].value

#from xunit import *
############################################################################


logger = logging.getLogger("nosyd")
LEVELS = {'debug': logging.DEBUG,
          'info': logging.INFO,
          'warning': logging.WARNING,
          'error': logging.ERROR,
          'critical': logging.CRITICAL}

'''
The daemon
'''
class Nosyd:
  projects = {}

  def __init__(self):
    self.check_period = 1
    from user import home
    self.nosyd_dir = str(home) + "/.nosyd"
    self.createDirStructure()
    logging.basicConfig(level=logging.INFO)

  def list(self):
    paths = self.resolved_project_paths()
    print "nosyd monitors " + str(len(paths)) + " project(s)"
    for p in paths:
      print p + self._status_dir_str(p)

  def clean(self):
    pns = self.project_names()
    for pn in pns:
      path = self.resolved_project_dir(pn)
      if not os.path.exists(path):
        print "Removing MISSING project: " + pn
        os.unlink(self.project_dir(pn))

  def _status_dir_str(self, path):
    if (not os.path.exists(path)):
      return "\t[MISSING]"
    return ""

  def local(self):
    np = NosyProject()
    np.run()

  def add(self, paths=[]):
    if (not paths or len(paths) == 0):
      paths = [ "." ]
    for path in paths:
      self.add_one(path)

  def add_one(self, path):
    path = os.path.abspath(path)
    paths = self.resolved_project_paths()
    if (path in paths):
      print " Path " + path + " already monitored. Not added"
    else:
      if (not os.path.exists(path)):
        print "Path " + path + " doesn't exist. Aborting"
        return
      if (not os.path.isdir(path)):
        print "Path " + path + " not a directory. Aborting"
        return
      print "Monitoring path " + path
      os.symlink(path, self.project_dir(os.path.basename(path)))

  def remove(self, paths=[]):
    if (not paths or len(paths) == 0):
      paths = [ "." ]
    for path in paths:
      self.remove_one(path)

  def remove_one(self, path=None):
    if (not path):
      path = "."
    path = os.path.abspath(path)
    paths = self.resolved_project_paths()
    if (path in paths):
#      if (not os.path.exists(path)):
#        print "Path " + path + " doesn't exist. Aborting"
      project_link = self.project_dir(os.path.basename(path))
      if (not os.path.islink(project_link)):
        print "Path " + path + " not a link. Aborting"
        return
      print "Un-monitoring path " + path
      os.unlink(project_link)
    else:
      print "Path " + path + " not monitored. So not removed"

  def jobs_dir(self):
    return self.nosyd_dir + "/jobs"

  def resolve_link(self, path):
    return os.path.realpath(path)

  def project_dir(self, project_name):
    return self.jobs_dir() + "/" + project_name

  def resolved_project_dir(self, project_name):
    return self.resolve_link(self.project_dir(project_name))

  def createDirectoryIfNecessary(self, pathname, description):
    if (os.path.exists(pathname)):
      if (not os.path.isdir(pathname)):
        raise NosydException("The " + description + "  (path " + pathname + ") exists but isn't a directory. Aborting")
    else:
      os.mkdir(pathname)

  def createDirStructure(self):
    self.createDirectoryIfNecessary(self.nosyd_dir, "nosyd directory")      
    self.createDirectoryIfNecessary(self.jobs_dir(), "nosyd jobs directory")
    
  def run(self):
    while (True):
      p = self.getNextProjectToBuild()
      print "Building " + p.project_dir
      p.buildAndNotify()

  def getNextProjectToBuild(self):
    while (True):
      p = self.updateProjectsChecksums()
      if (p):
        return p
      time.sleep(self.check_period)

  def is_project_link(self, path):
    return os.path.islink(self.project_dir(path))

  def project_names(self):
    return filter(self.is_project_link, os.listdir(self.jobs_dir()))

  def resolved_project_paths(self):
    return map(self.resolved_project_dir, self.project_names())

  def updateProjectsChecksums(self):
    project_names = self.project_names()
    logger.debug(str(len(project_names)) + " project(s) monitored")
    logger.debug(project_names)
    # keep links
    for pn in project_names:
      logger.debug("Verifying " + pn)
      if (self.projects.has_key(pn)):
        project = self.projects[pn]
        newVal = project.checkSum()
        if newVal != project.val:
          project.val = newVal
          return project
      else: # new project
        project_dir = self.resolved_project_dir(pn)
        if (not os.path.exists(project_dir)):
          logger.debug("Project dir " + project_dir + " doesn't exist. Skipping")
          continue
        logger.info("Project " + pn + " isn't yet monitored. Adding to build queue.")
        project = NosyProject(project_dir)
        project.val = project.checkSum()
        self.projects[pn] = project
        return project
    # remove unmonitored projects
    for monitored_pn in self.projects.keys():
      if (not monitored_pn in project_names):
        logger.info("Project " + monitored_pn + " isn't monitored anymore. Removing from build queue.")
        del self.projects[monitored_pn]
    return None
    
'''
Watch for changes in all monitored files. If changes, run the builder.build() method.
 '''
class NosyProject:

  def __init__(self, project_dir = None):
    self.project_dir = project_dir
    if (self.project_dir == None):
      pwd = os.path.abspath(".")
      self.project_dir = pwd

    # build specific properties
    self.val = 0
    self.oldRes = 0
    self.firstBuild = True
    self.keepOnNotifyingFailures = True
    self.importConfig(self.project_dir + "/.nosy")

    if (self.type == "trial"):
      self.builder = TrialBuilder()
    elif (self.type == "maven2"):
      self.builder = Maven2Builder()
    else:
      self.builder = NoseBuilder()

  def importConfig(self, configFile):
    # config specific properties
    import ConfigParser
    cp = ConfigParser.SafeConfigParser()
    cp.add_section('nosy')
    cp.set('nosy', 'type', 'nose')
    cp.set('nosy', 'monitor_paths', '*.py') # FIXME default is project type specific
    cp.set('nosy', 'logging', 'warning')
    cp.set('nosy', 'check_period', '1')

    if (os.access(configFile, os.F_OK)):
      cp.read(configFile)

    self.type = cp.get('nosy', 'type')

    level = LEVELS.get(cp.get('nosy', 'logging'), logging.NOTSET)
    logging.basicConfig(level=level)

    p = cp.get('nosy', 'monitor_paths')
    logger.info("Monitoring paths: " + p)
    self.paths = []
    for pattern in p.split():
      self.paths += FileSet(self.project_dir, pattern).find_paths()

    self.checkPeriod = cp.getint('nosy', 'check_period')

  def checkSum(self):
    ''' Return a long which can be used to know if any files from the paths variable have changed.'''
    val = 0

    if len(self.paths) == 0:
      logging.warning("No monitored paths for project_dir " + self.project_dir)
    for f in self.paths:
      stats = os.stat (f)
      val += stats [stat.ST_SIZE] + stats [stat.ST_MTIME]
#    print "checksum " + str(val)
    return val

  def notify(self,msg1,msg2,urgency=pynotify.URGENCY_LOW):
    if not pynotify.init("Markup"):
      return
    n = pynotify.Notification(msg1, msg2)
    n.set_urgency(urgency)
    if not n.show():
      print "Failed to send notification"

  def notifyFailure(self, r):
    if (r):
      msg1, msg2 = os.path.basename(self.project_dir) + " build failed.", self.project_dir + ": " + str(r.failures) + " tests failed and " + str(r.errors) + " errors: "
      msg2 += ", ".join(r.list_failure_names())
    else:
      msg1, msg2 = os.path.basename(self.project_dir) + " build failed.", self.project_dir + ": build failed."
    self.notify(msg1, msg2, pynotify.URGENCY_CRITICAL)

  def notifySuccess(self, r):
    if (r):
      msg1, msg2 = os.path.basename(self.project_dir) + " build successfull.", self.project_dir + ": " + str(r.tests - r.skip) + " tests passed."
    else:
      msg1, msg2 = os.path.basename(self.project_dir) + " build successful.", self.project_dir + ": build successful."
    self.notify(msg1, msg2)

  def notifyFixed(self, r):
    if (r):
      msg1, msg2 = os.path.basename(self.project_dir) + " build fixed.", self.project_dir + ": " + str(r.tests - r.skip) + " tests passed."
    else:
      msg1, msg2 = os.path.basename(self.project_dir) + " build Fixed.", self.project_dir + ": build fixed."
    self.notify(msg1, msg2, pynotify.URGENCY_NORMAL)

  def build(self):
    self.importConfig(self.project_dir + "/.nosy")
    os.chdir(self.project_dir)
    res, test_results = self.builder.build()
#    print "res:" + str(res)
    return res, test_results

  def buildAndNotify(self):
    res, test_results = self.build()
    if (res != 0):
      if (self.oldRes == 0 or self.keepOnNotifyingFailures):
        self.notifyFailure(test_results)
    else:
      if (self.firstBuild):
        self.notifySuccess(test_results)
      elif (self.oldRes != 0):
        self.notifyFixed(test_results)
    self.firstBuild = False
    self.oldRes = res

  def run(self):
    'allows to run nosy standalone'
    while (True):
      newVal = self.checkSum()
      if newVal != self.val:
        self.val = newVal
        res = self.buildAndNotify()
      time.sleep(self.checkPeriod)

class Builder:
  '''A builder has one method, build() that returns [res, test_results]. Res is 0 if the build passed and test_results contains a XunitTestSuite instance or None'''
  pass

class TrialBuilder:
  def build(self):
    return os.system ('trial'), None

class NoseBuilder(Builder):
  def build(self):
    res = os.system ('nosetests --with-xunit')
    test_results = parse_xunit_results('nosetests.xml')
    return res, test_results

class Maven2Builder(Builder):
  def build(self):
    res = os.system ('mvn test')
    test_results = None
    surefire_results = FileSet('target/surefire-reports', '/TEST-*.xml').find_paths()
    for result in surefire_results:
      r = parse_surefire_results(result)
      if (r == None):
        continue
      if (test_results == None):
        test_results = r
      else:
        test_results = test_results + r
    return res, test_results

from optparse import OptionParser

class MyOptionParser(OptionParser):
  def print_help(self, file=None):
    OptionParser.print_help(self, file)
    if file is None:
      file = sys.stdout
    file.write("\nDefault behavior:\n")
    file.write("\t\tStart nosyd\n")
    file.write("\nComments & bugs to <jerome.lacoste@gmail.com>\n")

if __name__ == '__main__':
  import sys

  parser = MyOptionParser(version='%prog 0.0.2')
  parser.add_option("-a", "--add", default=None, action="store_true",
                  help="Start monitoring the specified or current directory")
  parser.add_option("-r", "--remove", action="store_true",
                  help="Stop monitoring the specified or current directory")
  parser.add_option("-l", "--list", dest="list", action="store_true", default=False,
                  help="List the monitored projects")
  parser.add_option("-c", "--clean", dest="clean", action="store_true", default=False,
                  help="Clean the projects nosyd can't track anymore (links point to nowhere)")
  parser.add_option("-1", "--local", dest="local", action="store_true", default=False,
                  help="Run the standalone nosyd on the specified or current directory")

  (options, args) = parser.parse_args()

  nb_opts = 0
  if (options.add):
    nb_opts += 1
  if (options.remove):
    nb_opts += 1
  if (options.list):
    nb_opts += 1
  if (options.local):
    nb_opts += 1
  if (options.clean):
    nb_opts += 1
  if (nb_opts > 1):
    parser.error("options --add, --clean, --remove, -list and --local are mutually exclusive")

  nosyd = Nosyd()
  if (options.add):
    nosyd.add(args)
  elif (options.remove):
    nosyd.remove(args)
  elif (options.clean):
    nosyd.clean()
  elif (options.list):
    nosyd.list()
  elif (options.local):
    nosyd.local()
  else:
    try:
      nosyd.run()
    except KeyboardInterrupt:
      logger.info("Aborting...")
