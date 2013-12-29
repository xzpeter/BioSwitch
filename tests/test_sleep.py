#!/usr/bin/python

import time
import datetime
import sys
import threading

TEST_EVENT = 1
event = threading.Event()

if len(sys.argv) < 2:
    exit(1)
length = float(sys.argv[1])

def get_time ():
    return datetime.datetime.now()

print 'testing sleeping %s sec...' % length
time2 = get_time()
while 1:
    time1 = time2
    if TEST_EVENT:
	    event.wait(length)
    else:
	    time.sleep(length)
    time2 = get_time()
    delta = time2 - time1
    sec = delta.seconds + delta.microseconds * 1e-6
    print str(sec)
    
