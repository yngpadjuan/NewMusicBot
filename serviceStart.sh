#!/bin/bash

until ping -c1 8.8.8.8 >/dev/null 2>&1; do :; done
/usr/bin/python3 /home/pi/Music/BoxMusic/listeners.py &
