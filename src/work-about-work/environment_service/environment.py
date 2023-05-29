import re
from flask import request
from enum import Enum
import os

class Environment(Enum):
    DEVELOPMENT=1
    PRODUCTION=2
    UNKNOWN=3

def get_request_environment(request):
    # Remove this
    return get_environment()


def get_environment():
    if 'GAE_INSTANCE' in os.environ:
        return Environment.PRODUCTION
    else:
        return Environment.DEVELOPMENT
    
