#!/bin/bash

python3 -m venv venv

source venv/bin/activate

pip install -r requirements.txt

python initdb.py

python run.py