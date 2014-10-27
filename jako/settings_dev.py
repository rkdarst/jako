from .settings import *

DEBUG = True
TEMPLATE_DEBUG = DEBUG

FORCE_SCRIPT_NAME = '/dev/'

# If the site is behind a proxy, set this to True.  Note: remove in
# production.
USE_X_FORWARDED_HOST = True
