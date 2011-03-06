#!/usr/bin/env python
"""
Connect to nethack.alt.org
and farm some puddings
"""


from optparse import OptionParser
from pprint import pformat
import time


coslog = open('cosby.log', 'a')
def cosby_log(msg, var=None):
    logline = time.asctime() + ": " + msg + ": " + pformat(var)
    print >> coslog, logline

