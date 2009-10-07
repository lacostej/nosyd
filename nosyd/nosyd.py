#!/usr/bin/env python
# Initial idea from Jeff Winkler, http://jeffwinkler.net
# By Jerome Lacoste, jerome@coffeebreaks.org
# MIT license

import os,stat,time,os.path
import logging
import re

from xunit import *
from utils import *

version="0.0.4"

class NosydException(Exception):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return repr(self.value)


############################################################################

logger = logging.getLogger("nosyd")

LEVELS = {'debug':    logging.DEBUG,
          'info':     logging.INFO,
          'warning':  logging.WARNING,
          'error':    logging.ERROR,
          'critical': logging.CRITICAL}

'''
The daemon
'''
class Nosyd:
  # this is our build_queue :) We have only one builder and don't prioritize the builds. Just build the first one that has changed
  projects = {}

  def __init__(self):
    from user import home
    self.nosyd_dir = os.path.join(str(home), ".nosyd")
    self._create_nosyd_dir_structure()
    self._import_config()

  def _import_config(self):
    config_file = os.path.join(self.nosyd_dir, "config")
    import ConfigParser
    cp = ConfigParser.SafeConfigParser()
    cp.add_section('nosyd')
    cp.set('nosyd', 'logging', 'warning')
    cp.set('nosyd', 'check_period', '1')

    if (os.access(config_file, os.F_OK)):
      cp.read(config_file)

    level = LEVELS.get(cp.get('nosyd', 'logging'), logging.NOTSET)
    logging.basicConfig(level=level)
    logging.getLogger('').setLevel(level)
    logger.debug("reading config... level = " + str(level))

    self.check_period = cp.getint('nosyd', 'check_period')
    self.config = cp

  ###################### nosyd command line 'functions' ######################
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

  def stop(self):
    self._touch(self.stop_file())

  def local(self):
    np = NosyProject()
    np.run()

  def add(self, paths=[]):
    if (not paths or len(paths) == 0):
      paths = [ "." ]
    for path in paths:
      self._add_one(path)

  def _add_one(self, path):
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
      self._remove_one(path)

  def _remove_one(self, path=None):
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

  def _create_directory_if_necessary(self, pathname, description):
    if (os.path.exists(pathname)):
      if (not os.path.isdir(pathname)):
        raise NosydException("The " + description + " s(path " + pathname + ") exists but isn't a directory. Aborting")
    else:
      os.mkdir(pathname)

  def _create_nosyd_dir_structure(self):
    self._create_directory_if_necessary(self.nosyd_dir, "nosyd directory")
    self._create_directory_if_necessary(self.jobs_dir(), "nosyd jobs directory")

  ###################### nosyd 'daemon' ######################
  def run(self):
    'Run the nosyd daemon'
    stop_file = self.stop_file()
    if os.path.exists(stop_file):
      os.unlink(stop_file)

    while (True):
      p = self._get_next_project_to_build()
      logger.info("Building " + p.project_dir)
      p.buildAndNotify()
      if os.path.exists(stop_file):
        logger.info("Stop file found. Exiting.")
        break

  def _get_next_project_to_build(self):
    while (True):
      self._import_config()
      p = self._update_projects_checksums()
      if (p):
        return p
      time.sleep(self.check_period)

  def _update_projects_checksums(self):
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
        project = NosyProject(project_dir, pn)
        project.val = project.checkSum()
        self.projects[pn] = project
        return project
    # remove unmonitored projects
    for monitored_pn in self.projects.keys():
      if (not monitored_pn in project_names):
        logger.info("Project " + monitored_pn + " isn't monitored anymore. Removing from build queue.")
        del self.projects[monitored_pn]
    return None

  ######################## HELPER METHODS ########################
  def jobs_dir(self):
    return os.path.join(self.nosyd_dir, "jobs")

  def stop_file(self):
    return os.path.join(self.nosyd_dir, "stop")

  def resolve_link(self, path):
    return os.path.realpath(path)

  def project_dir(self, project_name):
    return os.path.join(self.jobs_dir(), project_name)

  def resolved_project_dir(self, project_name):
    return self.resolve_link(self.project_dir(project_name))

  def project_names(self):
    return filter(self.is_project_link, os.listdir(self.jobs_dir()))

  def resolved_project_paths(self):
    return map(self.resolved_project_dir, self.project_names())

  def is_project_link(self, path):
    return os.path.islink(self.project_dir(path))

  def _touch(self, path):
    '''Util command. Creates a file if it doesn't exist'''
    if not os.path.exists(path):
      open(path, 'w').close()

    
'''
Watch for changes in all monitored files. If changes, run the builder.build() method.
 '''
class NosyProject:
  URGENCY_LOW, URGENCY_NORMAL, URGENCY_CRITICAL = range(3)

  def __init__(self, project_dir = None, project_name = None):
    self.project_dir = project_dir
    self.project_name = project_name

    if (self.project_dir == None):
      pwd = os.path.abspath(".")
      self.project_dir = pwd
      self.project_name = "local"

    # build specific properties
    self.val = 0
    self.oldRes = 0
    self.firstBuild = True
    self.keepOnNotifyingFailures = True
    self._import_config()

  def _import_config(self):
    config_file = os.path.join(self.project_dir, ".nosy")
    # config specific properties
    import ConfigParser
    cp = ConfigParser.SafeConfigParser()
    cp.add_section('nosy')
    cp.set('nosy', 'type', 'nose')
    cp.set('nosy', 'logging', 'warning')
    cp.set('nosy', 'check_period', '1')

    if (os.access(config_file, os.F_OK)):
      cp.read(config_file)

    self.type = cp.get('nosy', 'type')

    if (self.type == "trial"):
      self.builder = TrialBuilder()
    elif (self.type == "maven2"):
      self.builder = Maven2Builder()
    else:
      self.builder = NoseBuilder()

    level = LEVELS.get(cp.get('nosy', 'logging'), logging.NOTSET)
    logging.basicConfig(level=level)

    self.logger = logging.getLogger('nosy-' + self.project_name)
    self.logger.setLevel(level)

    if (not cp.has_option('nosy', 'monitor_paths')):
      cp.set('nosy', 'monitor_paths', self.builder.get_default_monitored_paths())

    self.monitor_paths = cp.get('nosy', 'monitor_paths')
    self.logger.debug("Monitoring paths: " + self.monitor_paths)

    self.checkPeriod = cp.getint('nosy', 'check_period')

  def checkSum(self):
    ''' Return a long which can be used to know if any files from the paths variable have changed.'''
    val = 0

    paths = FileSet(self.project_dir, self.monitor_paths.split()).find_paths()

    if len(paths) == 0:
      logging.warning("No monitored paths for project_dir " + self.project_dir)
    for f in paths:
      try:
        stats = os.stat (f)
        val += stats [stat.ST_SIZE] + stats [stat.ST_MTIME]
      except OSError:
        continue
    self.logger.debug("checksum " + str(val))
    return val

  def notifyFailure(self, r):
    if (r):
      msg1, msg2 = os.path.basename(self.project_dir) + " build failed.", self.project_dir + ": " + str(r.failures) + " tests failed and " + str(r.errors) + " errors: "
      msg2 += ", ".join(r.list_failure_names())
    else:
      msg1, msg2 = os.path.basename(self.project_dir) + " build failed.", self.project_dir + ": build failed."
    self.notify(msg1, msg2, self.URGENCY_CRITICAL)

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
    self.notify(msg1, msg2, self.URGENCY_NORMAL)

  def notify(self,msg1,msg2,urgency=URGENCY_LOW):
    '''This attemps to use python-notify, a Linux only notification, or fall back to standard output'''
    try:
      self.pynotify(msg1, msg2, urgency)
    except:
      print msg1 + " " + msg2

  def pynotify(self, msg1, msg2, urgency):
    import pynotify
    pyurgencies = {
      self.URGENCY_LOW : pynotify.URGENCY_LOW,
      self.URGENCY_NORMAL : pynotify.URGENCY_NORMAL,
      self.URGENCY_CRITICAL : pynotify.URGENCY_CRITICAL,
    }
    pyurgency = pyurgencies[urgency]
    if not pynotify.init("Markup"):
      return
    n = pynotify.Notification(msg1, msg2)
    n.set_urgency(pyurgency)
    if not n.show():
      print "Failed to send notification"

  def build(self):
    self._import_config()
    os.chdir(self.project_dir)
    res, test_results = self.builder.build()
    self.logger.debug("build res:" + str(res))
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
  '''A builder has one method, build() that returns [res, test_results]. Res is 0 if the build passed and test_results contains a XunitTestSuite instance or None
     A builder also has a  get_default_monitored_paths method that returns a space separated list of FileSet patterns'''
  pass


class TrialBuilder:
  def get_default_monitored_paths(self):
    return "*.py **/*.py"

  def build(self):
    return os.system ('trial'), None

class NoseBuilder(Builder):
  def get_default_monitored_paths(self):
    return "*.py **/*.py"

  def build(self):
    res = os.system ('nosetests --with-xunit')
    test_results = parse_xunit_results('nosetests.xml')
    return res, test_results

class Maven2Builder(Builder):
  def get_default_monitored_paths(self):
    return "src/main/java/**/*.java src/test/java/**/*.java"

  def build(self):
    res = os.system ('mvn test')
    test_results = None
    surefire_results = FileSet('target/surefire-reports', 'TEST-*.xml').find_paths()
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

class NosydOptionParser(OptionParser):
  def print_help(self, file=None):
    OptionParser.print_help(self, file)
    if file is None:
      file = sys.stdout
    file.write("\nDefault behavior:\n")
    file.write("\t\tStart nosyd\n")
    file.write("\nComments & bugs to <jerome.lacoste@gmail.com>\n")

def main():
  parser = NosydOptionParser(version='%prog ' + version)
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
  parser.add_option("-s", "--stop", dest="stop", action="store_true", default=False,
                  help="Stops the running server, if any")

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
  if (options.stop):
    nb_opts += 1
  if (nb_opts > 1):
    parser.error("options --add, --clean, --remove, --list, --local and --stop are mutually exclusive")

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
  elif (options.stop):
    nosyd.stop()
  else:
    try:
      nosyd.run()
    except KeyboardInterrupt:
      logger.info("Aborting...")

if __name__ == '__main__':
  import sys
  main()

