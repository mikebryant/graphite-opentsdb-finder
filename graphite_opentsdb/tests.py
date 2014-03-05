'''Tests for graphite-opentsdb.'''
# pylint: disable=C0103
# pylint: disable=R0904

from django import test
from django.conf import settings
from django.test.utils import override_settings
from httmock import all_requests, with_httmock

from graphite_opentsdb.finder import OpenTSDBFinder
from graphite.storage import FindQuery

@all_requests
def mocked_urls(url, request):
    print url
    return {
        ('localhost:4242', '/tree/branch', 'branch=0001'): {
            'status_code': 200,
            'content': '''{"leaves":[{"metric":"leaf","tags":{"host":"localhost"},"tsuid":"000BC700000100047A","displayName":"leaf"}],"branches":[{"leaves":null,"branches":null,"path":{"0":"ROOT","1":"branch1"},"displayName":"branch1","treeId":1,"branchId":"0001CFE0B4A4","depth":1},{"leaves":null,"branches":null,"path":{"0":"ROOT","1":"branch2"},"displayName":"branch2","treeId":1,"branchId":"00013FFD49C8","depth":1}],"path":{"0":"ROOT"},"displayName":"ROOT","treeId":1,"branchId":"0001","depth":0}''',
        },
        ('localhost:4242', '/tree/branch', 'branch=0001CFE0B4A4'): {
            'status_code': 200,
            'content': '''{"leaves":[{"metric":"branch1.leaf","tags":{"host":"localhost"},"tsuid":"000BC700000100047B","displayName":"leaf"}],"branches":null,"path":{"0":"ROOT","1":"branch1"},"displayName":"branch1","treeId":1,"branchId":"0001CFE0B4A4","depth":1}''',
        },
        ('localhost:4242', '/tree/branch', 'branch=00013FFD49C8'): {
            'status_code': 200,
            'content': '''{"leaves":[{"metric":"branch2.leaf","tags":{"host":"localhost"},"tsuid":"000BC700000100047C","displayName":"leaf"}],"branches":null,"path":{"0":"ROOT","1":"branch2"},"displayName":"branch2","treeId":1,"branchId":"00013FFD49C8","depth":1}''',
        },
    }.get(
        (url.netloc, url.path, url.query),
        {
            'status_code': 500,
            'content': '',
        }
    )

class OpenTSDBFinderTestCase(test.TestCase):
    '''Test the finder class.'''

    def setUp(self):
        #self.settings_dict = copy.deepcopy(self.BASE_SETTINGS)
        self.finder = OpenTSDBFinder()

    @override_settings(
        OPENTSDB_URI  = 'http://localhost:9999',
        OPENTSDB_TREE = 999,
    )
    def test_finder_settings(self):
        '''
        Test that the finder can default to Django settings.
        '''
        print settings.OPENTSDB_URI
        print settings.OPENTSDB_TREE

        finder = OpenTSDBFinder()
        self.assertEqual(finder.opentsdb_uri, 'http://localhost:9999')
        self.assertEqual(finder.opentsdb_tree, 999)

    @with_httmock(mocked_urls)
    def test_finder_nodes(self):
        '''
        Test that the finder can find nodes.
        '''

        # Base query
        nodes = list(self.finder.find_nodes(query=FindQuery('*', None, None)))

        self.assertEqual(
            len(nodes),
            3,
            'There should be 3 nodes at the top level, not %d.' % len(nodes),
        )

        # One level down
        nodes = list(self.finder.find_nodes(query=FindQuery('*.leaf', None, None)))

        self.assertEqual(
            len(nodes),
            2,
            'There should be 2 nodes at this level, not %d.' % len(nodes),
        )

        nodes = list(self.finder.find_nodes(query=FindQuery('branch1.leaf', None, None)))

        self.assertEqual(
            len(nodes),
            1,
            'There should be 1 node at this level, not %d.' % len(nodes),
        )


