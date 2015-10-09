__author__ = 'susperius'

import gevent
import pickle
import logging
import os
from worker import Worker
from databaseworker import DB_TYPES, SEPARATOR
from node.model.message_types import MESSAGE_TYPES
from node.utils.html_css_splitter import split_files, is_two_files
from model.crash import Crash


class ReportWorker(Worker):
    def __init__(self, report_queue, db_queue, node_dict, crash_dict=None):
        self._logger = logging.getLogger(__name__)
        self._greenlet = None
        self._report_queue = report_queue
        self._db_queue = db_queue
        self._nodes = node_dict
        self._crashes = {} if crash_dict is None else crash_dict

    def __worker_green(self):
        while True:
            address, data_packed = self._report_queue.get()
            data_unpacked = pickle.loads(data_packed)
            msg_type = data_unpacked[0]
            if MESSAGE_TYPES['CRASH'] == msg_type:
                file_type = data_unpacked[1]
                program = data_unpacked[2]
                report = data_unpacked[3]
                self.__report_crash_local(address, file_type, program, report)
            elif MESSAGE_TYPES['GET_CONFIG'] == msg_type:
                config = data_unpacked[1]
                self._nodes[address].config = config
            gevent.sleep(1)

    def start_worker(self):
        if self._greenlet is None:
            self._greenlet = gevent.spawn(self.__worker_green)
            gevent.sleep(0)

    def stop_worker(self):
        if self._greenlet is not None:
            gevent.kill(self._greenlet)

    @property
    def crashes(self):
        return self._crashes

    @staticmethod
    def __parse_string_report(crash, value, end_marker="\r"):
        start = crash.find(value) + len(value)
        end = crash.find(end_marker, start)
        if end_marker == "\r" and end == -1:
            end = crash.find("\n", start)
        return crash[start:end]

    def __report_crash_local(self, node_address, file_type, program, crash):
        program = program.split("\\")[-1].split(".")[0]
        classification = self.__parse_string_report(crash[0], "Exploitability Classification: ")
        description = self.__parse_string_report(crash[0], "Short Description: ")
        hash_val = self.__parse_string_report(crash[0], "(Hash=", ")")
        hash_val = hash_val.split(".")
        self._nodes[node_address].crashed(hash_val[0])
        crash_key = program + SEPARATOR + hash_val[0]
        if crash_key not in self._crashes.keys():
            self._crashes[crash_key] = Crash(node_address, program, hash_val[0], hash_val[1],
                                                                 description, classification)
        else:
            self._crashes[crash_key].add_node_address(node_address)
        self._db_queue.put((DB_TYPES['CRASH'], crash_key))
        directory = "results/" + program + "/" + description + "/" + hash_val[0] + "/" + hash_val[1]
        if os.path.exists(directory):
            self._logger.info("duplicated crash")
        else:
            self._logger.info("New unique crash in " + program + "-> \r\n\tclass = " + classification +
                              " \r\n\tShort Description = " + description +
                              " \r\n\tsaved in " + directory)
            os.makedirs(directory)
            if is_two_files(crash[1]):
                files = split_files(crash[1], "crash_file." + file_type)
                with open(directory + "/" + files.keys()[0], 'wb+') as file1_fd, open(directory + "/" + files.keys()[1], 'wb+') as file2_fd:
                    file1_fd.write(files[files.keys()[0]])
                    file2_fd.write(files[files.keys()[1]])
            else:
                with open(directory + "/crash_file." + file_type, "wb+") as fd_crash:
                    fd_crash.write(crash[1])
            with open(directory + "/crash_report.txt", 'w+') as fd_rep:
                fd_rep.write(crash[0])
