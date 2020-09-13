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