#!/usr/bin/python
import signal
import time
import threading

def signal_handler(n, stack):
	print "get signal: " + str(n)
	print "stack: " + str(stack)
	exit (0)

def work ():
	print "thread working..."
	signal.signal(signal.SIGTERM, signal_handler)
	while 1:
		time.sleep(1)

signal.signal(signal.SIGTERM, signal_handler)

t = threading.Thread(target=work)
t.start()

while 1:
	time.sleep(100)
