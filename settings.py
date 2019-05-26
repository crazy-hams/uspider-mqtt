""" Microservice configurator file """
##
#
# This file configures the microservice.
#
# This microservice uses 'dotenv' (.env) files to get environmental variables.
# This is done to configure sensible parameters, like database connections,
# application secret keys and the like. In case the 'dotenv' file does not
# exists, a warning is generated at run-time.
#
# This application implements the '12 Factor App' principle:
# https://12factor.net and https://12factor.net/config
#
# Note about PyLint static code analyzer: items disable are false positives.
#
##

# pylint: disable=invalid-name;
# pylint: disable=too-few-public-methods;
# pylint: disable=C0301, R0912, R0914, R0915, R1702, W0703

import sys
from os import environ, path
from environs import Env


ENV_FILE = path.join(path.abspath(path.dirname(__file__)), '.env')

try:
    ENVIR = Env()
    ENVIR.read_env()
except Exception as e:
    print('Error: .env file not found: %s' % e)
    sys.exit(1)


class Config:
    """ This is the generic loader that sets common attributes """
    JSON_SORT_KEYS = False
    if environ.get('SERVERMQTT'):
        MQTT_HOST = ENVIR('SERVERMQTT')
    if environ.get('CALL'):
        CALL = ENVIR('CALL')

