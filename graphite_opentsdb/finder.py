from __future__ import division

from django.conf import settings
from graphite.intervals import Interval, IntervalSet
from graphite.node import BranchNode, LeafNode
from graphite.storage import FindQuery
import requests
import time

class OpenTSDBFinder(object):
    def __init__(self, opentsdb_uri=None, opentsdb_tree=None):
        self.opentsdb_uri = (opentsdb_uri or getattr(settings, 'OPENTSDB_URI', 'http://localhost:4242')).rstrip('/')
        self.opentsdb_tree = opentsdb_tree or getattr(settings, 'OPENTSDB_TREE', 1)

    def find_nodes(self, query):
        for node in self.find_opentsdb_nodes(query, "%04X" % self.opentsdb_tree):
            yield node

    def get_opentsdb_url(self, url):
        #print "%s/%s" % (self.opentsdb_uri, url)
        return requests.get("%s/%s" % (self.opentsdb_uri, url)).json()

    def find_opentsdb_nodes(self, query, current_branch, path=''):
        #print query.pattern, current_branch, type(query.pattern), query.pattern in ('*', ''), path
        for node, node_data in self.get_branch_nodes(current_branch, path):
            #print node, node_data
            adjusted_name = "%s." % node_data['displayName']
            if query.pattern in ('*', ''):
                yield node
            elif query.pattern == node_data['displayName']:
                yield node
            elif query.pattern.startswith('*.') and not node.is_leaf:
                for inner_node in self.find_opentsdb_nodes(
                    FindQuery(
                        pattern = query.pattern.replace('*.', '', 1),
                        startTime = query.startTime,
                        endTime = query.endTime,
                    ),
                    node_data['branchId'],
                    node.path,
                ):
                    yield inner_node
            elif query.pattern.startswith(adjusted_name):
                for inner_node in self.find_opentsdb_nodes(
                    FindQuery(
                        pattern = query.pattern.replace(adjusted_name, '', 1),
                        startTime = query.startTime,
                        endTime = query.endTime,
                    ),
                    node_data['branchId'],
                    node.path,
                ):
                    yield inner_node

    def get_branch_nodes(self, current_branch, path):
        results = self.get_opentsdb_url("tree/branch?branch=%s" % current_branch)
        if path:
            path += '.'
        if results['branches']:
            for branch in results['branches']:
                yield BranchNode(path + branch['displayName']), branch
        if results['leaves']:
            for leaf in results['leaves']:
                reader = OpenTSDBReader(
                    self.opentsdb_uri,
                    leaf['tsuid'],
                )
                yield LeafNode(path + leaf['displayName'], reader), leaf


class OpenTSDBReader(object):
    __slots__ = ('url',)
    supported = True
    step = 60

    def __init__(self, base_url, tsuid):
        self.url = "%s/query?tsuid=sum:1m-avg:%s" % (base_url, tsuid)

    def get_intervals(self):
        return IntervalSet([Interval(0, time.time())])

    def fetch(self, startTime, endTime):
        #print int(startTime), int(endTime), int(endTime-startTime)/self.step
        data = requests.get("%s&start=%d&end=%d" % (
            self.url,
            int(startTime),
            int(endTime),
        )).json()
        #print data
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
