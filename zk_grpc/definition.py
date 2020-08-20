# coding=utf-8
from collections import namedtuple
from typing import Type, TypeVar

StubType = TypeVar("StubType")
StubClass = Type[StubType]  # Stub class generate by protoc

ServicerType = TypeVar("ServicerType")
ServicerClass = Type[ServicerType]  # Servicer class generate by protoc


ZK_ROOT_PATH = "/ZK-Grpc"
SNODE_PREFIX = "Server"

ServerInfo = namedtuple("Server", "channel addr path")


class NoServerAvailable(Exception):
    pass

