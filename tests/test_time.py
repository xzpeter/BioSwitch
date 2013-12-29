#!/usr/bin/python
import datetime
import time

print "testing time accuracy"

result = []

for i in range(10,500,40):
	print "testing interval of %s ms..." % i
	time1 = datetime.datetime.now()
	time.sleep(i/1000.0)
	time2 = datetime.datetime.now()
	delta = time2 - time1
	delta = delta.seconds + 1e-6 * delta.microseconds
	result.append([i, delta])

print "results:"
print "========="
for res in result:
	print "%s  %s  (%s)" % (res[0], res[1], 
			abs(1.0*(res[0]-res[1]*1e3)/res[0]))
