BioSwitch
=========

This is a very tiny program for Doudou to help with his biological experiments.

Need below libraries before use:

* python-2.7
* wxPython, the GUI
* PySerial, the well-known serial port library in python

ChangeLog:

* v0.2:
** adding shortkeys from F1-F8 to quick load config files and start them
** adding shortkey F10 to stop a running task
** adding key to save the F1-F8 quick load config file paths.

* v0.3:
** Adding cycling feature to each channel's timing struct. And the cycle
can be nested (which is called signal, combined signals can be nested).
