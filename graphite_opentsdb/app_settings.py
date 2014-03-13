'''
Application settings for graphite-opentsdb.
'''

from django.conf import settings

#: URI to the OpenTSDB API
OPENTSDB_URI = getattr(
    settings,
    'OPENTSDB_URI',
    'http://localhost:4242/api/v1/',
)

#: Tree ID to display in graphite
OPENTSDB_TREE = getattr(
    settings,
    'OPENTSDB_TREE',
    1,
)
