# coding=utf-8
import re
from enum import IntEnum
from collections import namedtuple
from typing import Type, TypeVar

StubType = TypeVar("StubType")
StubClass = Type[StubType]  # Stub class generate by protoc

ServicerType = TypeVar("ServicerType")
ServicerClass = Type[ServicerType]  # Servicer class generate by protoc

ZK_ROOT_PATH = "/ZK-Grpc"
SNODE_PREFIX = "Server"

ServerInfo = namedtuple("Server", "channel addr path weight")

W_VALUE_RE = re.compile(r"^(.*?:\d+)\|\|(\d+)$")
VALUE_RE = re.compile(r"^(.*?:\d+)$")

DEFAILT_WEIGHT = 10


class LBS(IntEnum):
    '''Load balancing strategy enum'''
    RANDOM = 1
    WEIGHTED_RANDOM = 2


class NoServerAvailable(Exception):
    pass


class InitServiceFlag(object):

    def __init__(self, path: str):
        self._flag = False
        self._path = path

    def is_set(self):
        return self._flag

    def set(self):
        self._flag = True

    def clear(self):
        self._flag = False

    @property
    def path(self):
        return self._path