# coding=utf-8
import random
import typing
from typing import Union, Callable

import grpc.experimental.aio

from .definition import NoServerAvailable, LBS, UnregisteredLBSError

try:
    if typing.TYPE_CHECKING:
        from .aio import AIOZKGrpc
        from .basic import ZKGrpc
except AttributeError:
    pass

LBSFunc = Callable[[str, Union["ZKGrpc", "AIOZKGrpc"]],
                   Union[grpc.Channel, grpc.experimental.aio.Channel]]


class LBSRegistry(object):

    def __init__(self):
        self._lbs_funcs = dict()
        self._default_lbs = LBS.RANDOM

    def register(self, name: Union["LBS", str], lbs_func: LBSFunc) -> None:
        self._lbs_funcs[name] = lbs_func

    def unregister(self, name: Union["LBS", str]) -> None:
        self._lbs_funcs.pop(name, None)

    def get_channel(self, service_name: str, zk_grpc_obj: Union["ZKGrpc", "AIOZKGrpc"],
                    lbs: Union["LBS", str, None] = None) -> Union[grpc.Channel, grpc.experimental.aio.Channel]:
        if not lbs:
            lbs = self._default_lbs

        service_map = zk_grpc_obj.services[service_name]
        if not service_map:
            raise NoServerAvailable("There is no available servers for %s" % service_name)

        lbs_func = self._lbs_funcs.get(lbs)
        if not lbs_func:
            raise UnregisteredLBSError("Unregistered lbs_func name: {}".format(lbs))
        return lbs_func(service_name, zk_grpc_obj)


def random_lbs_func(service_name: str, zk_grpc_obj: Union["ZKGrpc", "AIOZKGrpc"]) -> Union[
    grpc.Channel, grpc.experimental.aio.Channel]:
    service_map = zk_grpc_obj.services[service_name]
    if not service_map:
        raise NoServerAvailable("There is no available servers for %s" % service_name)
    servers = service_map.keys()
    server = random.choice(list(servers))
    return service_map[server].channel


def weighted_random_lbs_func(service_name: str, zk_grpc_obj: Union["ZKGrpc", "AIOZKGrpc"]) -> Union[
    grpc.Channel, grpc.experimental.aio.Channel]:
    service_map = zk_grpc_obj.services[service_name]
    if not service_map:
        raise NoServerAvailable("There is no available servers for %s" % service_name)
    servers = service_map.keys()
    server = random.choices(list(servers), [server.weight for server in service_map.values()])[0]
    return service_map[server].channel


lbs_registry = LBSRegistry()
lbs_registry.register(LBS.RANDOM, random_lbs_func)
lbs_registry.register(LBS.WEIGHTED_RANDOM, weighted_random_lbs_func)
