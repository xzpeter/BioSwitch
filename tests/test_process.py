#!/usr/bin/python
import os
import time
import signal

pid = os.fork()
if 0 == pid:
	print "child running..."
	while 1:
		time.sleep(1)
print "parent.."
sleep(1)
print "killing child..."
os.kill(pid, signal.SIGTERM)
print "done"
