#!/usr/bin/env python
# By Jeff Winkler, http://jeffwinkler.net
# By Jerome Lacoste, jerome@coffeebreaks.org

import glob,os,stat,time,os.path
import pynotify
import logging

logger = logging.getLogger("simple_example")
LEVELS = {'debug': logging.DEBUG,
          'info': logging.INFO,
          'warning': logging.WARNING,
          'error': logging.ERROR,
          'critical': logging.CRITICAL}

pwd = os.path.abspath(".")

class XunitTestSuite:
  def __init__(self, name, tests, errors, failures, skip):
    self.name = name
    self.tests = tests
    self.errors = errors
    self.failures = failures
    self.skip = skip

  def __str__(self):
    return "XunitTestSuite: %s %s %s %s %s" % (self.name , self.tests, self.errors, self.failures, self.skip)

def parse_xunit_results(filename):
  try :
    from xml.dom import minidom
    xmldoc = minidom.parse(filename)
    testsuite = xmldoc.firstChild
    return XunitTestSuite(testsuite.attributes['name'].value, int(testsuite.attributes['tests'].value), int(testsuite.attributes['errors'].value), int(testsuite.attributes['failures'].value), int(testsuite.attributes['skip'].value))  
  except IOError:
    return None

'''
Watch for changes in all monitored files. If changes, run nosetests.
 '''
class Nosy:

  paths = []

  def importConfig(self, configFile):
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
      msg1, msg2 = os.path.basename(pwd) + " build failed.", pwd + ": " + str(r.failures) + " tests failed and " + str(r.errors) + " errors."
    else:
      msg1, msg2 = os.path.basename(pwd) + " build failed.", pwd + ": build failed."
    self.notify(msg1, msg2)

  def notifySuccess(self):
    r = parse_xunit_results('nosetests.xml')
    if (r):
      msg1, msg2 = os.path.basename(pwd) + " build successfull.", pwd + ": " + str(r.tests - r.skip) + " tests passed."
    else:
      msg1, msg2 = os.path.basename(pwd) + " build successful.", pwd + ": build successful."
    self.notify(msg1, msg2)

  def notifyFixed(self):
    r = parse_xunit_results('nosetests.xml')
    if (r):
      msg1, msg2 = os.path.basename(pwd) + " build fixed.", pwd + ": " + str(r.tests - r.skip) + " tests passed."
    else:
      msg1, msg2 = os.path.basename(pwd) + " build Fixed.", pwd + ": build fixed."
    self.notify(msg1, msg2)

  def run(self):
    val=0
    oldRes = 0
    firstBuild = True
    while (True):
      keepOnNotifyingFailures = True
      newVal = self.checkSum()
      if newVal != val:
        val=newVal
        res = os.system ('nosetests --with-xunit')
#        print "res:" + str(res)
        if (res != 0):
          if (oldRes == 0 or keepOnNotifyingFailures):
            self.notifyFailure()
        else:
          if (firstBuild):
            self.notifySuccess()
          elif (oldRes != 0):
            self.notifyFixed()
        firstBuild = False
      time.sleep(self.checkPeriod)
      oldRes = res

if __name__ == '__main__':
  nosy = Nosy()
  nosy.importConfig(r".nosy")
  nosy.run()
