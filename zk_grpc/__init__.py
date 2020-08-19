# coding=utf-8
import random
import threading
from typing import Type
from inspect import isclass
from collections import defaultdict

import grpc
from grpc._server import _Server
from kazoo.client import KazooClient
from kazoo.protocol.states import EventType, WatchedEvent

from .definition import (ZK_ROOT_PATH, SNODE_PREFIX,
                         Server,
                         NoServerAvailable,
                         StubType)


class ZKGrpc(object):

    def __init__(self, kz_client: KazooClient,
                 zk_root_path: str = ZK_ROOT_PATH, node_prefix: str = SNODE_PREFIX,
                 channel_factory = grpc.insecure_channel, channel_factory_kwargs: dict = None):
        self._kz_client = kz_client
        self.zk_root_path = zk_root_path
        self.node_prefix = node_prefix

        self.channel_factory = channel_factory
        self.channel_factory_kwargs = channel_factory_kwargs or {}

        self.services = defaultdict(dict)
        self._locks = defaultdict(threading.RLock)

    def init_stub(self, stub_class: Type[StubType], service_name: str = None):
        if not service_name:
            class_name = stub_class.__name__
            service_name = "".join(class_name.rsplit("Stub", 1))

        channel = self.get_channel(service_name)
        return stub_class(channel)

    def _split_service_name(self, service_path: str):
        return service_path.rsplit("/", 1)[-1]

    def _split_server_name(self, server_path: str):
        service_path, server_name = server_path.rsplit("/", 1)
        service_name = self._split_service_name(service_path)
        return service_path, service_name, server_name

    def _remove_channel(self, server: Server):
        if server and isinstance(server, Server):
            ch = server.channel
            ch.close()

    def child_watcher(self, event: WatchedEvent):
        service_name = self._split_service_name(event.path)

        if event.type == EventType.CHILD:
            # update
            childs = self._kz_client.get_children(event.path, watch=self.child_watcher)
            with self._locks[service_name]:
                fetched_servers = self.services[service_name].keys()
                new_servers = set(childs)
                expr_servers = fetched_servers - new_servers  # servers to delete
                for server in new_servers:
                    if server in fetched_servers:
                        continue
                    self.set_channel(service_path=event.path, child_name=server, service_name=service_name)

                _sers = [self.services[service_name].pop(server, None) for server in expr_servers]
            for _ser in _sers:
                self._remove_channel(_ser)

        elif event.type == EventType.DELETED:
            # delete
            with self._locks[service_name]:
                _sers = self.services.pop(service_name, [])
                self._locks.pop(service_name, None)
            for _ser in _sers:
                self._remove_channel(_ser)

    def child_value_watcher(self, event: WatchedEvent):
        if event.type == EventType.CHANGED:
            # update
            service_path, service_name, server_name = self._split_server_name(event.path)
            self.set_channel(service_path=service_path, child_name=server_name, service_name=service_name)

        elif event.type == EventType.DELETED:
            # delete
            # do nothing, child_watcher will handle all the things
            pass

    def set_channel(self, service_path, child_name, service_name, event=None):
        child_path = "/".join((service_path, child_name))
        data, _ = self._kz_client.get(child_path, watch=self.child_value_watcher)
        server_addr = data.decode("utf-8")

        ori_ser_info = self.services[service_name].get(child_name)
        if ori_ser_info and isinstance(ori_ser_info, Server):
            ori_addr = ori_ser_info.addr
            if server_addr == ori_addr: return

        channel = self.channel_factory(server_addr, **self.channel_factory_kwargs)
        self.services[service_name].update({child_name: Server(channel=channel, addr=server_addr)})

        if isinstance(event, threading.Event) and not event.is_set():
            event.set()

    def fetch_servers(self, service_name: str):

        service_path = "/".join((self.zk_root_path.rstrip("/"), service_name))
        self._kz_client.ensure_path(service_path)

        childs = self._kz_client.get_children(service_path, watch=self.child_watcher)

        if not childs:
            raise NoServerAvailable("There is no available servers for %s" % service_name)

        _event = threading.Event()
        for child in childs:
            th = threading.Thread(target=self.set_channel,
                                  kwargs={"service_path": service_path,
                                          "child_name": child,
                                          "service_name": service_name,
                                          "event": _event})
            th.setDaemon(True)
            th.start()
        # wait for first value
        _event.wait()  # Todo: set timeout

    def get_channel(self, service_name: str):
        service = self.services.get(service_name)
        if service is None:

            with self._locks[service_name]:
                service = self.services.get(service_name)
                if service is not None:
                    return self._get_channel(service, service_name)
                # get server from zk
                self.fetch_servers(service_name)
                return self._get_channel(self.services[service_name], service_name)

        return self._get_channel(service, service_name)

    def _get_channel(self,
                     service_map: dict,
                     service_name: str
                     ):

        servers = service_map.keys()
        if not servers:
            raise NoServerAvailable("There is no available servers for %s" % service_name)
        server = random.choice(list(servers))
        return service_map[server].channel


class ZKRegister(object):

    def __init__(self, kz_client: KazooClient,
                 zk_root_path: str = ZK_ROOT_PATH, node_prefix: str = SNODE_PREFIX):

        self._kz_client = kz_client
        self.zk_root_path = zk_root_path
        self.node_prefix = node_prefix

        self._creted_nodes = set()
        self._services = set()

    def register_grpc_server(self, server: grpc._server._Server, host: str, port: int):
        value_str = "{}:{}".format(host, port)
        for s in server._state.generic_handlers:
            service_name = s.service_name()
            self._create_server_node(service_name=service_name, value=value_str)

    def register_server(self, service, host: str, port: int):
        value_str = "{}:{}".format(host, port)

        if isclass(service):
            class_name = service.__name__
            service_name = "".join(class_name.rsplit("Servicer", 1))
        else:
            service_name = str(service)

        self._create_server_node(service_name=service_name, value=value_str)

    def _create_server_node(self, service_name: str, value: bytes):
        if not isinstance(value, bytes):
            value = value.encode("utf-8")
        service_path = "/".join((self.zk_root_path.rstrip("/"), service_name))
        if service_path not in self._services:
            self._kz_client.ensure_path(service_path)
        path = "/".join((service_path, self.node_prefix.strip("/")))
        path = self._kz_client.create(path, value, ephemeral=True, sequence=True)
        self._creted_nodes.add(path)

    def shutdown(self):
        rets = list()
        print("nodes: ", self._creted_nodes)
        for node in self._creted_nodes:
            ret = self._kz_client.delete_async(node)
            rets.append(ret)
        for ret in rets:
            ret.get()
