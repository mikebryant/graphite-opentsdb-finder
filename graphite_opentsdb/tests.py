'''Tests for graphite-opentsdb.'''
# pylint: disable=C0103
# pylint: disable=R0904

from django import test
from httmock import all_requests, with_httmock
import mock

from graphite_opentsdb.finder import OpenTSDBFinder
from graphite.storage import FindQuery
from graphite_opentsdb import app_settings


@all_requests
def mocked_urls(url, request):
    return {
        ('localhost:4242', '/api/v1/tree/branch', 'branch=0001'): {
            'status_code': 200,
            'content': '''{"leaves":[{"metric":"leaf","tags":{"host":"localhost"},"tsuid":"000BC700000100047A","displayName":"leaf"}],"branches":[{"leaves":null,"branches":null,"path":{"0":"ROOT","1":"branch1"},"displayName":"branch1","treeId":1,"branchId":"0001CFE0B4A4","depth":1},{"leaves":null,"branches":null,"path":{"0":"ROOT","1":"branch2"},"displayName":"branch2","treeId":1,"branchId":"00013FFD49C8","depth":1}],"path":{"0":"ROOT"},"displayName":"ROOT","treeId":1,"branchId":"0001","depth":0}''',
        },
        ('localhost:4242', '/api/v1/tree/branch', 'branch=0001CFE0B4A4'): {
            'status_code': 200,
            'content': '''{"leaves":[{"metric":"branch1.leaf","tags":{"host":"localhost"},"tsuid":"000BC700000100047B","displayName":"leaf"}],"branches":null,"path":{"0":"ROOT","1":"branch1"},"displayName":"branch1","treeId":1,"branchId":"0001CFE0B4A4","depth":1}''',
        },
        ('localhost:4242', '/api/v1/tree/branch', 'branch=00013FFD49C8'): {
            'status_code': 200,
            'content': '''{"leaves":[{"metric":"branch2.leaf","tags":{"host":"localhost"},"tsuid":"000BC700000100047C","displayName":"leaf"}],"branches":null,"path":{"0":"ROOT","1":"branch2"},"displayName":"branch2","treeId":1,"branchId":"00013FFD49C8","depth":1}''',
        },
        ('localhost:4242', '/api/v1/tree/branch', 'branch=0002'): {
            'status_code': 200,
            'content': '''{"leaves":null,"branches":[{"leaves":null,"branches":null,"path":{"0":"ROOT","1":"leaf.with.dots"},"displayName":"leaf.with.dots","treeId":1,"branchId":"0002CFE0B4A4","depth":1}],"path":{"0":"ROOT"},"displayName":"ROOT","treeId":2,"branchId":"0002","depth":0}''',
        },
        ('localhost:4242', '/api/v1/tree/branch', 'branch=0003'): {
            'status_code': 404,
            'content': '',
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
        self.finder = OpenTSDBFinder('http://localhost:4242/api/v1', 1)

    @mock.patch.object(app_settings, 'OPENTSDB_URI', 'http://localhost:9999')
    @mock.patch.object(app_settings, 'OPENTSDB_TREE', 999)
    def test_finder_settings(self):
        '''
        Test that the finder can default to Django settings.
        '''

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
            [node.path for node in nodes],
            ['branch1', 'branch2', 'leaf'],
        )

        # One level down
        nodes = list(self.finder.find_nodes(query=FindQuery('*.leaf', None, None)))

        self.assertEqual(
            [node.path for node in nodes],
            ['branch1.leaf', 'branch2.leaf']
        )

        nodes = list(self.finder.find_nodes(query=FindQuery('branch1.leaf', None, None)))

        self.assertEqual(
            [node.path for node in nodes],
            ['branch1.leaf'],
        )

    @with_httmock(mocked_urls)
    def test_finder_braces(self):
        '''
        Test that the finder can deal with brace expressions.
        '''

        nodes = list(self.finder.find_nodes(query=FindQuery('{branch1,leaf}', None, None)))
        self.assertEqual(
            [node.path for node in nodes],
            ['branch1', 'leaf'],
        )

    @with_httmock(mocked_urls)
    def test_finder_character_classes(self):
        '''
        Test that the finder can deal with character classes.
        '''

        nodes = list(self.finder.find_nodes(query=FindQuery('branch[1]', None, None)))
        self.assertEqual(
            [node.path for node in nodes],
            ['branch1'],
        )

    @with_httmock(mocked_urls)
    def test_finder_dotted_nodes(self):
        '''
        Test that the finder can deal with nodes with dots
        (Since OpenTSDB allows that).
        '''

        finder = OpenTSDBFinder('http://localhost:4242/api/v1/', 2)

        nodes = list(finder.find_nodes(query=FindQuery('*', None, None)))
        self.assertEqual(
            [node.name for node in nodes],
            ['leaf.with.dots'],
        )

    @with_httmock(mocked_urls)
    def test_finder_missing_branch(self):
        '''
        Test that the finder can deal with a missing branch.
        '''

        finder = OpenTSDBFinder('http://localhost:4242/api/v1/', 3)

        nodes = list(finder.find_nodes(query=FindQuery('*', None, None)))
        self.assertEqual(nodes, [])
