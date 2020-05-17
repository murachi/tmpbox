#!/bin/bash
export PIPENV_VENV_IN_PROJECT=1
pipenv sync
sudo pipenv run python setup.py
