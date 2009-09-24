# By Jeff Winkler, http://jeffwinkler.net

import glob,os,stat,time

'''
Watch for changes in all .py files. If changes, run nosetests. 
'''
def checkSum():
    ''' Return a long which can be used to know if any .py files have changed.
    Only looks in the current directory. '''
    val = 0
    for f in glob.glob ('*.py'):
        stats = os.stat (f)
        val += stats [stat.ST_SIZE] + stats [stat.ST_MTIME]
    for f in glob.glob ('*.kid'):
        stats = os.stat (f)
        val += stats [stat.ST_SIZE] + stats [stat.ST_MTIME]

    return val

val=0
while (True):
    if checkSum() != val:
        val=checkSum()
        os.system ('nosetests')
    time.sleep(1)
