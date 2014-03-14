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

#: Cache time for OpenTSDB fetches.
OPENTSDB_CACHE_TIME = getattr(
    settings,
    'OPENTSDB_CACHE_TIME',
    60*15,
)
