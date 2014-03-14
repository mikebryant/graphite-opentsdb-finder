from __future__ import division

from cacheback.decorators import cacheback
from django.conf import settings
from graphite.intervals import Interval, IntervalSet
from graphite.node import BranchNode, LeafNode
import re
import requests
import time

from . import app_settings

import logging
LOGGER = logging.getLogger(__name__)


class OpenTSDBNodeMixin(object):
    def __init__(self, name, *args):
        super(OpenTSDBNodeMixin, self).__init__(*args)
        self.name = name


class OpenTSDBLeafNode(OpenTSDBNodeMixin, LeafNode):
    pass


class OpenTSDBBranchNode(OpenTSDBNodeMixin, BranchNode):
    pass


@cacheback(app_settings.OPENTSDB_CACHE_TIME)
def cached_find_nodes(opentsdb_uri, opentsdb_tree, pattern):
    query_parts = []
    for part in pattern.split('.'):
        part = part.replace('*', '.*')
        part = re.sub(
            r'{([^{]*)}',
            lambda x: "(%s)" % x.groups()[0].replace(',', '|'),
            part,
        )
        query_parts.append(part)
    return list(find_opentsdb_nodes(opentsdb_uri, query_parts, "%04X" % opentsdb_tree))


def get_opentsdb_url(opentsdb_uri, url):
    full_url = "%s/%s" % (opentsdb_uri, url)
    try:
        return requests.get(full_url).json()
    except ValueError:
        LOGGER.error("Couldn't parse json for %s", full_url)


def find_opentsdb_nodes(opentsdb_uri, query_parts, current_branch, path=''):
    query_regex = re.compile(query_parts[0])
    for node, node_data in get_branch_nodes(opentsdb_uri, current_branch, path):
        node_name = node_data['displayName']
        dot_count = node_name.count('.')

        if dot_count:
            node_query_regex = re.compile(r'\.'.join(query_parts[:dot_count+1]))
        else:
            node_query_regex = query_regex

        if node_query_regex.match(node_name):
            if len(query_parts) == 1:
                yield node
            elif not node.is_leaf:
                for inner_node in find_opentsdb_nodes(
                    opentsdb_uri,
                    query_parts[dot_count+1:],
                    node_data['branchId'],
                    node.path,
                ):
                    yield inner_node


def get_branch_nodes(opentsdb_uri, current_branch, path):
    results = get_opentsdb_url(opentsdb_uri, "tree/branch?branch=%s" % current_branch)
    if results:
        if path:
            path += '.'
        if results['branches']:
            for branch in results['branches']:
                yield OpenTSDBBranchNode(branch['displayName'], path + branch['displayName']), branch
        if results['leaves']:
            for leaf in results['leaves']:
                reader = OpenTSDBReader(
                    opentsdb_uri,
                    leaf['tsuid'],
                )
                yield OpenTSDBLeafNode(leaf['displayName'], path + leaf['displayName'], reader), leaf


class OpenTSDBFinder(object):
    def __init__(self, opentsdb_uri=None, opentsdb_tree=None):
        self.opentsdb_uri = (opentsdb_uri or app_settings.OPENTSDB_URI).rstrip('/')
        self.opentsdb_tree = opentsdb_tree or app_settings.OPENTSDB_TREE

    def find_nodes(self, query):
        for node in cached_find_nodes(self.opentsdb_uri, self.opentsdb_tree, query.pattern):
            yield node


class OpenTSDBReader(object):
    __slots__ = ('url',)
    supported = True
    step = 60

    def __init__(self, base_url, tsuid):
        self.url = "%s/query?tsuid=sum:1m-avg:%s" % (base_url, tsuid)

    def get_intervals(self):
        return IntervalSet([Interval(0, time.time())])

    def fetch(self, startTime, endTime):
        data = requests.get("%s&start=%d&end=%d" % (
            self.url,
            int(startTime),
            int(endTime),
        )).json()

        time_info = (startTime, endTime, self.step)
        number_points = int((endTime-startTime)//self.step)
        datapoints = [None for i in range(number_points)]

        for series in data:
            for timestamp, value in series['dps'].items():
                timestamp = int(timestamp)
                interval = timestamp - (timestamp % 60)
                index = (interval - int(startTime)) // self.step
                datapoints[index] = value

        return (time_info, datapoints)
