# coding=utf-8
import asyncio
from typing import Union, Optional, List, cast
from inspect import isclass
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait

import grpc.experimental.aio
from kazoo.client import KazooClient

from .definition import (ZK_ROOT_PATH, SNODE_PREFIX,
                         ServerInfo,
                         NoServerAvailable,
                         StubClass, ServicerClass)
from . import ZKGrpcMixin


class AIOZKGrpc(ZKGrpcMixin):

    def __init__(self, kz_client: KazooClient,
                 zk_root_path: str = ZK_ROOT_PATH, node_prefix: str = SNODE_PREFIX,
                 channel_factory: Union[
                     grpc.experimental.aio.insecure_channel, grpc.experimental.aio.secure_channel
                 ] = grpc.experimental.aio.insecure_channel,
                 channel_factory_kwargs: dict = None,
                 grace: Optional[float] = None,
                 thread_pool: Optional[ThreadPoolExecutor] = None,
                 loop: Optional[asyncio.AbstractEventLoop] = None):

        super(AIOZKGrpc, self).__init__(kz_client=kz_client,
                                        zk_root_path=zk_root_path, node_prefix=node_prefix,
                                        channel_factory=channel_factory, channel_factory_kwargs=channel_factory_kwargs,
                                        thread_pool=thread_pool)
        self.channel_grace = grace
        self._loop = loop
        self._is_aio = True

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value):
        self._loop = value
    async def wrap_stub(self, stub_class: StubClass, service_name: str = None):
        if not service_name:
            class_name = stub_class.__name__
            service_name = "".join(class_name.rsplit("Stub", 1))

        channel = await self.get_channel(service_name)

        return cast(stub_class, stub_class(channel))

    async def _close_channel(self, server: ServerInfo):
        if server and isinstance(server, ServerInfo):
            ch = server.channel
            await ch.close(self.channel_grace)

    def _close_channels(self, servers: List[ServerInfo]):
        fus = list()
        for _ser in servers:
            fu = asyncio.run_coroutine_threadsafe(self._close_channel(_ser), self.loop)
            fus.append(fu)
        wait(fus)

    async def fetch_servers(self, service_name: str):

        service_path = "/".join((self.zk_root_path.rstrip("/"), service_name))

        fu = asyncio.wrap_future(
            self._thread_pool.submit(self._kz_client.ensure_path,
                                     service_path)
        )
        await fu

        fu = asyncio.wrap_future(
            self._thread_pool.submit(self._kz_client.get_children,
                                     path=service_path,
                                     watch=self.child_watcher)
        )
        childs = await fu

        if not childs:
            raise NoServerAvailable("There is no available servers for %s" % service_name)

        fus = list()
        for child in childs:
            fu = asyncio.wrap_future(
                self._thread_pool.submit(self.set_channel,
                                         service_path=service_path,
                                         child_name=child,
                                         service_name=service_name,
                                         loop=self.loop)
            )
            fus.append(fu)

        # wait for first completed
        await asyncio.wait(fus, return_when=FIRST_COMPLETED)  # Todo: set timeout

    async def get_channel(self, service_name: str):
        service = self.services.get(service_name)
        if service is None:
            with self._locks[service_name]:
                service = self.services.get(service_name)
                if service is not None:
                    return self._get_channel(service, service_name)
                # get server from zk
                await self.fetch_servers(service_name)
                return self._get_channel(self.services[service_name], service_name)

        return self._get_channel(service, service_name)

    async def stop(self):
        servers = list()
        for _, _sers in self.services.items():
            servers.extend((self._close_channel(_ser) for _ser in _sers))
        self.services.clear()
        await asyncio.wait(servers)


class AIOZKRegister(object):

    def __init__(self, kz_client: KazooClient,
                 zk_root_path: str = ZK_ROOT_PATH, node_prefix: str = SNODE_PREFIX,
                 thread_pool: Optional[ThreadPoolExecutor] = None):

        self._kz_client = kz_client
        self.zk_root_path = zk_root_path
        self.node_prefix = node_prefix

        self._creted_nodes = set()
        self._services = set()

        self._thread_pool = thread_pool or ThreadPoolExecutor()  # for running sync func in main thread

    async def register_server(self, service: Union[ServicerClass, str], host: str, port: int):
        value_str = "{}:{}".format(host, port)

        if isclass(service):
            class_name = service.__name__
            service_name = "".join(class_name.rsplit("Servicer", 1))
        else:
            service_name = str(service)
        fu = self._thread_pool.submit(self._create_server_node,
                                      service_name=service_name,
                                      value=value_str)
        await asyncio.wrap_future(fu)

    def _create_server_node(self, service_name: str, value: Union[str, bytes]):
        if not isinstance(value, bytes):
            value = value.encode("utf-8")
        service_path = "/".join((self.zk_root_path.rstrip("/"), service_name))
        if service_path not in self._services:
            self._kz_client.ensure_path(service_path)
        path = "/".join((service_path, self.node_prefix.strip("/")))
        path = self._kz_client.create(path, value, ephemeral=True, sequence=True)
        self._creted_nodes.add(path)

    async def stop(self):
        fus = list()
        for node in self._creted_nodes:
            fu = self._thread_pool.submit(self._kz_client.delete, node)
            new_fu = asyncio.wrap_future(fu)
            fus.append(new_fu)
        await asyncio.wait(fus)
