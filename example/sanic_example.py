import asyncio
from sanic import Sanic
from sanic.response import json

from example_pb2 import HelloRequest
from example_pb2_grpc import HelloServiceStub

from kazoo.client import KazooClient
from zk_grpc.aio import AIOZKGrpc


app = Sanic("App Name")

kz = KazooClient(hosts="127.0.0.1:2181")
zk_g = AIOZKGrpc(kz_client=kz)


@app.listener('after_server_start')
async def server_start(app, loop):
    kz.start()
    zk_g.loop = loop

@app.listener('before_server_stop')
async def server_stop(app, loop):
    await zk_g.stop()
    kz.stop()
    kz.close()


@app.route("/")
async def test(request):

    stub = await zk_g.wrap_stub(HelloServiceStub)

    resp = await stub.hello_world(HelloRequest(hello="hello"))

    return json({"hello": resp.hello})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)