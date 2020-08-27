# coding=utf-8
import asyncio
from example_pb2 import HelloRequest
from example_pb2_grpc import HelloServiceStub

from kazoo.client import KazooClient
from zk_grpc.aio import AIOZKGrpc


async def run():
    # before useing
    kz = KazooClient(hosts="127.0.0.1:2181")

    kz.start()

    zk_g = AIOZKGrpc(kz_client=kz)
    zk_g.loop = asyncio.get_event_loop()

    # get stub
    stub = await zk_g.wrap_stub(HelloServiceStub)

    # call grpc api
    resp = await stub.hello_world(HelloRequest(hello="hello"))
    print(resp.hello)

    # before exit
    await zk_g.stop()
    kz.stop()
    kz.close()


if __name__ == '__main__':
    asyncio.run(run())