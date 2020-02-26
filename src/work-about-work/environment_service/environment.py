import re
from flask import request
from enum import Enum

class Environment(Enum):
    DEVELOPMENT=1
    PRODUCTION=2

def get_request_environment(request):
    if re.search("^http(s)?://localhost(:\d+)?/", request.base_url):
        return Environment.DEVELOPMENT
