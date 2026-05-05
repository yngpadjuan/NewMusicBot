#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd $DIR

until ping -c1 8.8.8.8 >/dev/null 2>&1; do :; done
python3 ${DIR}/listeners.py
