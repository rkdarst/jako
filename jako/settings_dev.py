from .settings import *

# Update settings.DEBUG so that logging is directed properly.
from . import settings
DEBUG = settings.DEBUG = True
del settings
TEMPLATE_DEBUG = DEBUG

FORCE_SCRIPT_NAME = '/dev/'

ALLOWED_HOSTS.append('127.0.0.1')

# If the site is behind a proxy, set this to True.  Note: remove in
# production.
USE_X_FORWARDED_HOST = True

#LOGGING['handlers']
