from __future__ import division

from cacheback.decorators import cacheback
from django.conf import settings
from graphite.intervals import Interval, IntervalSet
from graphite.node import BranchNode, LeafNode
from graphite.readers import FetchInProgress
import re
import requests
import time
import threading

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


def find_nodes_from_pattern(opentsdb_uri, opentsdb_tree, pattern):
    query_parts = []
    for part in pattern.split('.'):
        part = part.replace('*', '.*')
        part = re.sub(
            r'{([^{]*)}',
            lambda x: "(%s)" % x.groups()[0].replace(',', '|'),
            part,
        )
        query_parts.append(part)

    shared_reader = SharedReader()
    nodes = list(find_opentsdb_nodes(opentsdb_uri, query_parts, "%04X" % opentsdb_tree, shared_reader=shared_reader))
    shared_reader.node_count = len(nodes)
    for node in nodes:
        yield node


@cacheback(app_settings.OPENTSDB_CACHE_TIME)
def get_opentsdb_url(opentsdb_uri, url):
    full_url = "%s/%s" % (opentsdb_uri, url)
    return requests.get(full_url).json()


def find_opentsdb_nodes(opentsdb_uri, query_parts, current_branch, shared_reader, path=''):
    query_regex = re.compile(query_parts[0])
    for node, node_data in get_branch_nodes(opentsdb_uri, current_branch, shared_reader, path):
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
                # We might need to split into two branches here
                # if using dotted nodes, as we can't tell if the UI
                # wanted all nodes with a single * (from advanced mode)
                # or if a node like a.b is supposed to be matched by *.*
                if query_parts[dot_count+1:]:
                    for inner_node in find_opentsdb_nodes(
                        opentsdb_uri,
                        query_parts[dot_count+1:],
                        node_data['branchId'],
                        shared_reader,
                        node.path,
                    ):
                        yield inner_node
                if dot_count and query_parts[0] == '.*':
                    for inner_node in find_opentsdb_nodes(
                        opentsdb_uri,
                        query_parts[1:],
                        node_data['branchId'],
                        shared_reader,
                        node.path,
                    ):
                        yield inner_node


def get_branch_nodes(opentsdb_uri, current_branch, shared_reader, path):
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
                    leaf,
                    shared_reader,
                )
                yield OpenTSDBLeafNode(leaf['displayName'], path + leaf['displayName'], reader), leaf


class OpenTSDBFinder(object):
    def __init__(self, opentsdb_uri=None, opentsdb_tree=None):
        self.opentsdb_uri = (opentsdb_uri or app_settings.OPENTSDB_URI).rstrip('/')
        self.opentsdb_tree = opentsdb_tree or app_settings.OPENTSDB_TREE

    def find_nodes(self, query):
        for node in find_nodes_from_pattern(self.opentsdb_uri, self.opentsdb_tree, query.pattern):
            yield node


class SharedReader(object):
    def __init__(self):
        self.worker = threading.Semaphore(1)
        self.config_lock = threading.Lock()
        self.workers = {}
        self.results = {}
        self.result_events = {}

    def get(self, opentsdb_uri, aggregation_interval, leaf_data, start, end):
        key = (opentsdb_uri, aggregation_interval, leaf_data['metric'], start, end)
        with self.config_lock:
            if key not in self.workers:
                self.workers[key] = threading.Semaphore(1)
                self.result_events[key] = threading.Event()

        if self.workers[key].acquire(False):
            # we are the worker, do the work
            data = requests.get("%s/query?m=sum:%ds-avg:%s{%s}&start=%d&end=%d&show_tsuids=true" % (
                opentsdb_uri,
                aggregation_interval,
                leaf_data['metric'],
                ','.join(["%s=*" % t for t in leaf_data['tags']]),
                start,
                end,
            )).json()

            self.results[key] = {}
            for metric in data:
                assert len(metric['tsuids']) == 1
                self.results[key][metric['tsuids'][0]] = [metric]
            self.result_events[key].set()

        self.result_events[key].wait()
        tsuid = leaf_data['tsuid']
        if tsuid in self.results[key]:
            return self.results[key][tsuid]
        else:
            return []

class OpenTSDBReader(object):
    __slots__ = ('opentsdb_uri', 'leaf_data', 'shared_reader',)
    supported = True
    step = app_settings.OPENTSDB_DEFAULT_AGGREGATION_INTERVAL

    def __init__(self, opentsdb_uri, leaf_data, shared_reader):
        self.opentsdb_uri = opentsdb_uri
        self.leaf_data = leaf_data
        self.shared_reader = shared_reader

    def get_intervals(self):
        return IntervalSet([Interval(0, time.time())])

    def fetch(self, startTime, endTime):
        def get_data():

            if self.shared_reader.node_count > app_settings.OPENTSDB_METRIC_QUERY_LIMIT:
                data = self.shared_reader.get(
                    self.opentsdb_uri,
                    app_settings.OPENTSDB_DEFAULT_AGGREGATION_INTERVAL,
                    self.leaf_data,
                    int(startTime),
                    int(endTime),
                )
            else:
                data = requests.get("%s/query?tsuid=sum:%ds-avg:%s&start=%d&end=%d" % (
                    self.opentsdb_uri,
                    app_settings.OPENTSDB_DEFAULT_AGGREGATION_INTERVAL,
                    self.leaf_data['tsuid'],
                    int(startTime),
                    int(endTime),
                )).json()

            time_info = (startTime, endTime, self.step)
            number_points = int((endTime-startTime)//self.step)
            datapoints = [None for i in range(number_points)]

            for series in data:
                for timestamp, value in series['dps'].items():
                    timestamp = int(timestamp)
                    interval = timestamp - (timestamp % app_settings.OPENTSDB_DEFAULT_AGGREGATION_INTERVAL)
                    index = (interval - int(startTime)) // self.step
                    datapoints[index] = value

            return (time_info, datapoints)

        job = app_settings.OPENTSDB_REQUEST_POOL.apply_async(get_data)

        return FetchInProgress(job.get)
