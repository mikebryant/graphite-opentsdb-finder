DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
    },
}

# For graphite
# pylint: disable=W0401,W0614
from graphite.settings import *
LOG_DIR = '/tmp'

INSTALLED_APPS = ['graphite_opentsdb']
