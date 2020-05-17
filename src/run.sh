#!/bin/bash
if [ ${EUID:-${UID}} != 0 ]; then
  echo 'Cannot run without superuser. Please call me with sudo, or after change to superuser.'
  exit 1
fi
export PIPENV_VENV_IN_PROJECT=1
pipenv run uwsgi --ini conf.d/uwsgi-debug.ini
