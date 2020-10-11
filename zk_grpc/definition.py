# coding=utf-8
import re
from enum import Enum
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


class LBS(Enum):
    '''Load balancing strategy enum'''
    RANDOM = "random"
    WEIGHTED_RANDOM = "weighted_random"


class UnregisteredLBSError(Exception):
    pass


class NoServerAvailable(Exception):
    pass


class InitServiceFlag(object):

    def __init__(self, path: str):
        self._flag = False
        self._path = path

    def is_set(self) -> bool:
        return self._flag

    def set(self) -> None:
        self._flag = True

    def clear(self) -> None:
        self._flag = False

    @property
    def path(self) -> str:
        return self._path
