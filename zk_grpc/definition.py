# coding=utf-8
from collections import namedtuple
from typing import Type, TypeVar, NewType

StubType = TypeVar("StubType")


ZK_ROOT_PATH = "/ZK-Grpc"
SNODE_PREFIX = "Server"

Server = namedtuple("Server", "channel addr")


class NoServerAvailable(Exception):
    pass

