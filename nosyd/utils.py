import os
import re

def findall(seq, f):
    """Return all the element in seq where f(item) == True."""
    result = []
    for element in seq:
      if f(element):
        result.append(element)
    return result


'''
An a-la ant FileSet class that allows to identify groups of files that matches patterns. Supports recursivity
** means match all
* means match all except os.sep
'''
class FileSet:
  def __init__(self, dir, pattern):
    self.dir = dir
    self.pattern = pattern

  def _to_re_build_pattern(self, arg):
    '''Ugly function to convert ** into .* and * into [^/]* and use the result as input to a python RE'''
    re_pattern = []
    i = 0
    while i < len(arg):
      if (arg[i] == "*"):
        i = i + 1
        if (i < len(arg) - 1 and arg[i] == "*"):
          i = i + 1
          re_pattern.append(".*")
        else:
          re_pattern.append("[^/]*")
      re_pattern.append(arg[i])
      i = i + 1
    re_pattern.append("$")
    return ''.join(re_pattern)

  def _to_os_unspecific_path(self, os_specific_path):
    return os_specific_path.replace(os.sep, "/")

  def find_paths(self):
    tmp = os.path.join(self.dir, self.pattern)
    re_pattern = self._to_re_build_pattern(tmp)
    paths = []
    for root, dirs, files in os.walk(self.dir):
      for f in files:
        full_path = os.path.join(root, f)
        os_unspecific_path = self._to_os_unspecific_path(full_path)
        if (re.match(re_pattern, full_path)):
          paths.append(full_path)

#    print "PATHS : " + self.pattern + ": " + str(paths)
    return paths

