# coding=utf-8
import random
import threading
import asyncio
from typing import Union, Optional, cast, Iterable
from inspect import isclass
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
from collections import defaultdict
from functools import partial

import grpc.experimental.aio
from grpc._server import _Server
from kazoo.client import KazooClient
from kazoo.protocol.states import EventType, WatchedEvent, ZnodeStat, KazooState

from .definition import (ZK_ROOT_PATH, SNODE_PREFIX,
                         ServerInfo,
                         NoServerAvailable,
                         StubClass, ServicerClass, InitServiceFlag,
                         LBS, W_VALUE_RE, VALUE_RE, DEFAILT_WEIGHT)


class ZKRegisterMixin(object):

    def __init__(self, kz_client: KazooClient,
                 zk_root_path: str = ZK_ROOT_PATH, node_prefix: str = SNODE_PREFIX,
                 thread_pool: Optional[ThreadPoolExecutor] = None):

        self._kz_client = kz_client
        self.zk_root_path = zk_root_path
        self.node_prefix = node_prefix

        self._creted_nodes = set()
        self._lock = threading.RLock()
        self._stopped = False

        self._thread_pool = thread_pool or ThreadPoolExecutor()  # for running sync func in main thread
        self._kz_client.add_listener(self._session_watcher)

    def _create_server_node(self, service_name: str, value: Union[str, bytes]):
        if not isinstance(value, bytes):
            value = value.encode("utf-8")
        service_path = "/".join((self.zk_root_path.rstrip("/"), service_name))
        pre_path = "/".join((service_path, self.node_prefix.strip("/")))
        path = self._kz_client.create(pre_path, value, ephemeral=True, sequence=True, makepath=True)
        self._creted_nodes.add((service_name, path, value))

    def _session_watcher(self, state):
        if state == KazooState.CONNECTED and not self._stopped:
            self._kz_client.handler.spawn(self.resume_nodes)

    def resume_nodes(self):
        with self._lock:
            expired = set()
            created = self._creted_nodes.copy()
            for node in created:
                service_name, path, value = node
                stat = self._kz_client.exists(path)
                if stat:
                    continue
                expired.add(node)
                self._create_server_node(service_name=service_name, value=value)
            self._creted_nodes.difference_update(expired)


class ZKGrpcMixin(object):

    def __init__(self, kz_client: KazooClient,
                 zk_root_path: str = ZK_ROOT_PATH, node_prefix: str = SNODE_PREFIX,
                 channel_factory: Union[
                     grpc.insecure_channel, grpc.secure_channel,
                     grpc.experimental.aio.insecure_channel, grpc.experimental.aio.secure_channel
                 ] = grpc.insecure_channel,
                 channel_factory_kwargs: dict = None,
                 thread_pool: Optional[ThreadPoolExecutor] = None,
                 lbs: Optional[LBS] = None):
        self._kz_client = kz_client
        self.zk_root_path = zk_root_path
        self.node_prefix = node_prefix

        self.channel_factory = channel_factory
        self.channel_factory_kwargs = channel_factory_kwargs or {}

        self.services = defaultdict(dict)
        self._locks = defaultdict(threading.RLock)

        self._thread_pool = thread_pool or ThreadPoolExecutor()  # for running sync func in main thread
        self._is_aio = False
        self.loop = None

        self.lbs = lbs or LBS.RANDOM

    def _split_service_name(self, service_path: str):
        return service_path.rsplit("/", 1)[-1]

    def _split_server_name(self, server_path: str):
        service_path, server_name = server_path.rsplit("/", 1)
        service_name = self._split_service_name(service_path)
        return service_path, service_name, server_name

    def _get_channel(self, service_map: dict, service_name: str, lbs: Optional[LBS] = None):
        lbs = lbs or self.lbs
        if not isinstance(lbs, LBS):
            raise TypeError("Arg: lbs should be a member of zk_grpc.LBS")
        if not service_map:
            raise NoServerAvailable("There is no available servers for %s" % service_name)
        # TODO: Load balancing strategy
        servers = service_map.keys()
        server = random.choice(list(servers))
        return service_map[server].channel

    def _close_channels(self, servers: Iterable[ServerInfo]):
        # close grpc channels in subthread
        pass

    def set_server(self, service_path: str, child_name: str):
        child_path = "/".join((service_path, child_name))
        watcher = partial(self.data_watcher, path=child_path)
        self._kz_client.DataWatch(child_path, func=watcher)

    def data_watcher(self, data: Optional[bytes], stat: Optional[ZnodeStat], event: Optional[WatchedEvent], path: str):
        if event is None or event.type == EventType.CHANGED or event.type == EventType.NONE:
            if stat is None:
                _, service_name, server_name = self._split_server_name(path)
                services = self.services.get(service_name)
                if services is not None:
                    s_info = services.pop(server_name, None)
                    self._close_channels((s_info,))
                return False
            self._set_channel(data, path)
        elif event.type == EventType.DELETED:
            return False

    def _set_channel(self, data: bytes, path: str):
        if self._is_aio:
            asyncio.set_event_loop(self.loop)

        service_path, service_name, server_name = self._split_server_name(path)

        data = data.decode("utf-8")
        weight_re_ret = W_VALUE_RE.match(data)
        old_re_ret = VALUE_RE.match(data)
        if weight_re_ret:
            server_addr, weight = weight_re_ret.groups()
        elif old_re_ret:
            server_addr, weight = old_re_ret.group(), DEFAILT_WEIGHT
        else:
            return

        servers = self.services.get(service_name)
        channel = None
        if servers is not None:
            ori_ser_info = servers.get(server_name)
            if ori_ser_info and isinstance(ori_ser_info, ServerInfo):
                ori_addr, ori_weight = ori_ser_info.addr, ori_ser_info.weight
                if server_addr == ori_addr and ori_weight == weight:
                    return
                elif server_addr == ori_addr:
                    channel = ori_ser_info.channel
        if channel is None:
            channel = self.channel_factory(server_addr, **self.channel_factory_kwargs)

        self.services[service_name].update(
            {server_name: ServerInfo(channel=channel, addr=server_addr, path=path, weight=weight)}
        )

    def get_children(self, path: str):
        watcher = partial(self.children_watcher, init_flag=InitServiceFlag(path))
        child_watcher = self._kz_client.ChildrenWatch(path, func=watcher, send_event=True)

        return child_watcher._prior_children

    def children_watcher(self, childs: list, event: WatchedEvent, init_flag: InitServiceFlag = None):
        if not init_flag.is_set():
            init_flag.set()
            return

        path = init_flag.path
        service_name = self._split_service_name(path)

        if event is None or event.type == EventType.CHILD:
            # update
            with self._locks[service_name]:
                fetched_servers = self.services[service_name].keys()
                new_servers = set(childs)
                expr_servers = fetched_servers - new_servers  # servers to delete
                for server in new_servers:
                    if server in fetched_servers:
                        continue
                    self.set_server(service_path=path, child_name=server)

                _sers = [self.services[service_name].pop(server, None) for server in expr_servers]

            self._close_channels(_sers)

        elif event.type == EventType.DELETED:
            # delete
            with self._locks[service_name]:
                _sers = self.services.pop(service_name, {})
                self._locks.pop(service_name, None)

            self._close_channels(_sers.values())
            return False  # to remove watcher


class ZKGrpc(ZKGrpcMixin):

    def __init__(self, kz_client: KazooClient,
                 zk_root_path: str = ZK_ROOT_PATH, node_prefix: str = SNODE_PREFIX,
                 channel_factory: Union[grpc.insecure_channel, grpc.secure_channel] = grpc.insecure_channel,
                 channel_factory_kwargs: dict = None,
                 thread_pool: Optional[ThreadPoolExecutor] = None,
                 lbs: Optional[LBS] = None):
        super(ZKGrpc, self).__init__(kz_client=kz_client,
                                     zk_root_path=zk_root_path, node_prefix=node_prefix,
                                     channel_factory=channel_factory, channel_factory_kwargs=channel_factory_kwargs,
                                     thread_pool=thread_pool,
                                     lbs=lbs)

    def wrap_stub(self, stub_class: StubClass, service_name: str = None, lbs: Optional[LBS] = None):
        if not service_name:
            class_name = stub_class.__name__
            service_name = "".join(class_name.rsplit("Stub", 1))

        channel = self.get_channel(service_name, lbs=lbs)
        return cast(stub_class, stub_class(channel))

    def _close_channel(self, server: ServerInfo):
        if server and isinstance(server, ServerInfo):
            server.channel.close()

    def _close_channels(self, servers: Iterable[ServerInfo]):
        for _ser in servers:
            self._close_channel(_ser)

    def fetch_servers(self, service_name: str):

        service_path = "/".join((self.zk_root_path.rstrip("/"), service_name))
        self._kz_client.ensure_path(service_path)

        childs = self.get_children(path=service_path)

        if not childs:
            raise NoServerAvailable("There is no available servers for %s" % service_name)

        fus = [
            self._thread_pool.submit(self.set_server,
                                     service_path=service_path,
                                     child_name=child) for child in childs
        ]
        wait(fus, return_when=FIRST_COMPLETED)  # Todo: set timeout

    def get_channel(self, service_name: str, lbs: Optional[LBS] = None):
        service = self.services.get(service_name)
        if service is None:
            with self._locks[service_name]:
                service = self.services.get(service_name)
                if service is not None:
                    return self._get_channel(service, service_name)
                # get server from zk
                self.fetch_servers(service_name)
                return self._get_channel(self.services[service_name], service_name, lbs=lbs)

        return self._get_channel(service, service_name, lbs=lbs)

    def stop(self):
        for _, _sers in self.services.items():
            for _ser in _sers:
                self._close_channel(_ser)
        self.services.clear()


class ZKRegister(ZKRegisterMixin):

    def register_grpc_server(self, server: grpc._server._Server, host: str, port: int, weight: int = DEFAILT_WEIGHT):
        value_str = "{}:{}||{}".format(host, port, weight)

        with self._lock:
            fus = [
                self._thread_pool.submit(
                    self._create_server_node,
                    service_name=s.service_name(), value=value_str
                ) for s in server._state.generic_handlers
            ]
            if fus: wait(fus)

    def register_server(self, service: Union[ServicerClass, str], host: str, port: int, weight: int = DEFAILT_WEIGHT):
        value_str = "{}:{}||{}".format(host, port, weight)

        if isclass(service):
            class_name = service.__name__
            service_name = "".join(class_name.rsplit("Servicer", 1))
        else:
            service_name = str(service)

        with self._lock:
            self._create_server_node(service_name=service_name, value=value_str)

    def stop(self):
        self._stopped = True
        rets = [self._kz_client.delete_async(path) for _, path, _ in self._creted_nodes]
        for ret in rets:
            ret.get()
