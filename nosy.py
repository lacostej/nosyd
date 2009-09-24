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

class Nosy:

  paths = []

  def importConfig(self, configFile):
    import ConfigParser
    cp = ConfigParser.SafeConfigParser({'monitor_paths': '*.py', 'logging': 'warning'})
    if (os.access(configFile, os.F_OK)):
      cp.read(configFile)

    level = LEVELS.get(cp.get('nosy', 'logging'), logging.NOTSET)
    logging.basicConfig(level=level)

    p = cp.get('nosy', 'monitor_paths')
    logger.info("Monitoring paths: " + p)
    for path in p.split():
      self.paths += glob.glob(path)

  '''
  Watch for changes in all monitored files. If changes, run nosetests.
  '''
  def checkSum(self):
    ''' Return a long which can be used to know if any files from the paths variable have changed.'''
    val = 0

    for f in self.paths:
      stats = os.stat (f)
      val += stats [stat.ST_SIZE] + stats [stat.ST_MTIME]
    return val

def notify(msg1,msg2):
    if not pynotify.init("Markup"):
        return
    n = pynotify.Notification(msg1, msg2)
    if not n.show():
        print "Failed to send notification"

def notifyFailure():
    notify(os.path.basename(pwd) + " build failed.", pwd + ": nosetests failed")

def notifySuccess():
    notify(os.path.basename(pwd) + " build successfull.", pwd + ": nosetests success")

def run(nosy):
  val=0
  oldRes = 0
  firstBuild = True
  while (True):
    keepOnNotifyingFailures = True
    newVal = nosy.checkSum()
    if newVal != val:
      val=newVal
      res = os.system ('nosetests')
#        print "res:" + str(res)
      if (res != 0):
        if (oldRes == 0 or keepOnNotifyingFailures):
          notifyFailure()
      else:
        if (oldRes != 0 or firstBuild):
          notifySuccess()
      firstBuild = False
  time.sleep(1)
  oldRes = res

if __name__ == '__main__':
  nosy = Nosy()
  nosy.importConfig(r".nosy")
  run(nosy)
