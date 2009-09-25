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
      print p

  def add(self, path=None):
    if (not path):
      path = "."
    path = os.path.abspath(path)
    paths = self.resolved_project_paths()
    if (path in paths):
      print " Path " + path + " already monitored. Not added"
    else:
      if (not os.path.exists(path)):
        print "Path " + path + " doesn't exist. Aborting"
      if (not os.path.isdir(path)):
        print "Path " + path + " not a directory. Aborting"
      print "Monitoring path " + path
      os.symlink(path, self.project_dir(os.path.basename(path)))

  def remove(self, path=None):
    if (not path):
      path = "."
    path = os.path.abspath(path)
    paths = self.resolved_project_paths()
    if (path in paths):
#      if (not os.path.exists(path)):
#        print "Path " + path + " doesn't exist. Aborting"
      if (not os.path.islink(path)):
        print "Path " + path + " not a link. Aborting"
      print "Un-monitoring path " + path
      # note: this assumes that link dir == basename(project_dir). We could search for it otherwise
      os.unlink(self.project_dir(os.path.basename(path)))
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
        project = NosyProject(self.resolved_project_dir(pn))
        self.projects[pn] = project
        return project
    return None
    
'''
Watch for changes in all monitored files. If changes, run nosetests.
 '''
class NosyProject:

  paths = []

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

  def importConfig(self, configFile):
    # config specific properties
    import ConfigParser
    cp = ConfigParser.SafeConfigParser()
    cp.add_section('nosy')
    cp.set('nosy', 'monitor_paths', '*.py')
    cp.set('nosy', 'logging', 'warning')
    cp.set('nosy', 'check_period', '1')

    if (os.access(configFile, os.F_OK)):
      cp.read(configFile)

    level = LEVELS.get(cp.get('nosy', 'logging'), logging.NOTSET)
    logging.basicConfig(level=level)

    p = cp.get('nosy', 'monitor_paths')
    logger.info("Monitoring paths: " + p)
    for path in p.split():
      self.paths += glob.glob(path)

    self.checkPeriod = cp.getint('nosy', 'check_period')

  def checkSum(self):
    ''' Return a long which can be used to know if any files from the paths variable have changed.'''
    val = 0

    for f in self.paths:
      stats = os.stat (f)
      val += stats [stat.ST_SIZE] + stats [stat.ST_MTIME]
#    print "checksum " + str(val)
    return val

  def notify(self,msg1,msg2):
    if not pynotify.init("Markup"):
      return
    n = pynotify.Notification(msg1, msg2)
    if not n.show():
      print "Failed to send notification"

  def notifyFailure(self):
    r = parse_xunit_results('nosetests.xml')
    if (r):
      msg1, msg2 = os.path.basename(self.project_dir) + " build failed.", self.project_dir + ": " + str(r.failures) + " tests failed and " + str(r.errors) + " errors: "
      msg2 += ", ".join(r.list_failure_names())
    else:
      msg1, msg2 = os.path.basename(self.project_dir) + " build failed.", self.project_dir + ": build failed."
    self.notify(msg1, msg2)

  def notifySuccess(self):
    r = parse_xunit_results('nosetests.xml')
    if (r):
      msg1, msg2 = os.path.basename(self.project_dir) + " build successfull.", self.project_dir + ": " + str(r.tests - r.skip) + " tests passed."
    else:
      msg1, msg2 = os.path.basename(self.project_dir) + " build successful.", self.project_dir + ": build successful."
    self.notify(msg1, msg2)

  def notifyFixed(self):
    r = parse_xunit_results('nosetests.xml')
    if (r):
      msg1, msg2 = os.path.basename(self.project_dir) + " build fixed.", self.project_dir + ": " + str(r.tests - r.skip) + " tests passed."
    else:
      msg1, msg2 = os.path.basename(self.project_dir) + " build Fixed.", self.project_dir + ": build fixed."
    self.notify(msg1, msg2)

  def build(self):
    os.chdir(self.project_dir)
    res = os.system ('nosetests --with-xunit')
#        print "res:" + str(res)
    return res

  def buildAndNotify(self):
    res = self.build()
    if (res != 0):
      if (self.oldRes == 0 or self.keepOnNotifyingFailures):
        self.notifyFailure()
    else:
      if (self.firstBuild):
        self.notifySuccess()
      elif (self.oldRes != 0):
        self.notifyFixed()
    self.firstBuild = False
    self.oldRes = res

  def run(self):
    'allows to run nosy standalone'
    self.importConfig(r".nosy")
    while (True):
      newVal = self.checkSum()
      if newVal != self.val:
        self.val = newVal
        res = self.buildAndNotify()
      time.sleep(self.checkPeriod)

def usage():
  print "Usage:"
  print "  " + os.path.basename(sys.argv[0]) + " [OPTION] - minimal personal CI server"
  print ""
  print "Help options:"
  print "  -?, --help\t\t\tShow help options"
  print ""
  print "Application options:"
  print "  --local [path]\t\tRun nosy (standalone) on the current directory"
  print "  --add   [path]\t\tMonitor the specified or current directory"
  print "  --remove      \t\t\tUn-monitor the specified or current directory"
  print "  --list        \t\tList the project monitored"
  print ""
  print "Default behavior:"
  print "            \t\t\tStart nosyd"
  print ""
  print "Report bugs to <jerome.lacoste@gmail.com>"

if __name__ == '__main__':
  import sys
  # FIXME if --simple, runs a NosyProject instead
  command = None
  if len(sys.argv) > 1 and sys.argv[1]:
    command = sys.argv[1]
  if (command == "--local"):
    nosy = NosyProject()
    nosy.run()
  elif (command == "--list"):
    nosyd = Nosyd()
    nosyd.list()
  elif (command == "--add"):
    nosyd = Nosyd()
    d = None
    if len(sys.argv) > 2 and sys.argv[2]:
      d = sys.argv[2]
    nosyd.add(d)
  elif (command == "--remove"):
    nosyd = Nosyd()
    d = None
    if len(sys.argv) > 2 and sys.argv[2]:
      d = sys.argv[2]
    nosyd.remove(d)
  elif (command == "--help" or command == "-?" or command != None):
    usage()
  else:
    nosyd = Nosyd()
    try:
      nosyd.run()
    except KeyboardInterrupt:
      logger.info("Aborting...")
