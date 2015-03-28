__author__ = 'susperius'

import gevent
import logging

from gevent.queue import Queue
from model.task import Task
from model.node import PyFuzz2Node


class BeaconWorker:
    def __init__(self, beacon_queue):
        self._beacon_queue = beacon_queue
        self._logger = logging.getLogger(__name__)
        self._active = False
        self._node_dict = {}

    def __beacon_worker_green(self):
        while True:
            if not self._beacon_queue.empty():
                    actual_task = self._beacon_queue.get_nowait()
                    self.__beacon_worker(actual_task)
            gevent.sleep(0)

    def __beacon_worker(self, task):
        beacon = (task.get_task()['sender'], task.get_task()['msg'].split(':')[0], task.get_task()['msg'].split(':')[0])
        if not beacon[1] in self._node_dict:
            self._node_dict[beacon[1]] = PyFuzz2Node(beacon[1], beacon[0], beacon[2])
        else:
            self._node_dict[beacon[1]].beacon_received()
        self._logger.debug(self._node_dict[beacon[0]].dump())

    def __check_all_beacons(self):
        while True:
            for key, node in self._node_dict.items():
                if not node.check_status() and not node.check_status(120):
                    del self._node_dict[key]
                    self._logger.debug("Node: " + node.name + " deleted because of inactivity")
            gevent.sleep(40)

    @property
    def nodes(self):
        return self._node_dict

    def start_worker(self):
        if not self._active:
            gevent.spawn(self.__beacon_worker_green)
            gevent.spawn(self.__check_all_beacons)
            self._active = True
            gevent.sleep(0)