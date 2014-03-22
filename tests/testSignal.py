#!/usr/bin/env python

from bio_switch import Signal
import json

signal1 = Signal(length=20, state=1)
signal2 = Signal(length=30, state=0)
signal3 = Signal(length=18, state=1)

signal4 = Signal(sub_signals=[signal1, signal2, signal3], cycle=3)
signal5 = Signal(sub_signals=[signal1, signal4], cycle=2)

print "testing __str__()"
print signal5
print "testing dump()"
print json.dumps(signal5.dump(), indent=4)

print "testing parse"
config1 = '''
{
    "sub_signals": [
        {
            "length": 20,
            "state": 1
        },
        {
            "length": 10,
            "state": 0
        },
        {
            "length": 15,
            "state": 1
        }
    ],
    "cycle": 3
}
'''
config2 = '''
{
    "length": 50,
    "state": 1
}
'''
config3 = '''
{
    "sub_signals": [
        {
            "sub_signals": [
                {
                    "length": 30,
                    "state": 0
                },
                {
                    "length": 20,
                    "state": 1
                }
            ],
            "cycle": 2
        },
        {
            "length": 10,
            "state": 0
        }
    ],
    "cycle": 3
}
'''

for config in [config1, config2, config3]:
    print "testing parse config: "
    print config
    hash = json.loads(config)
    signal = Signal.parseFromHash(hash)
    print "parse result:"
    print signal
