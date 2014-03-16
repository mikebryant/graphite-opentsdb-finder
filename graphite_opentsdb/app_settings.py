'''
Application settings for graphite-opentsdb.
'''

from django.conf import settings

from multiprocessing.pool import ThreadPool

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

#: How many concurrent requests to allow.
OPENTSDB_MAX_REQUESTS = getattr(
    settings,
    'OPENTSDB_MAX_REQUESTS',
    10,
)

#: The pool to use for concurrent requests.
#: Overrides OPENTSDB_CURRENT_REQUESTS if set.
OPENTSDB_REQUEST_POOL = getattr(
    settings,
    'OPENTSDB_REQUEST_POOL',
    ThreadPool(OPENTSDB_MAX_REQUESTS),
)
