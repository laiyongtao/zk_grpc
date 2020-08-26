# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
import grpc

import example_pb2 as example__pb2


class HelloServiceStub(object):
    """Missing associated documentation comment in .proto file"""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.hello_world = channel.unary_unary(
                '/HelloService/hello_world',
                request_serializer=example__pb2.HelloRequest.SerializeToString,
                response_deserializer=example__pb2.HelloResponse.FromString,
                )


class HelloServiceServicer(object):
    """Missing associated documentation comment in .proto file"""

    def hello_world(self, request, context):
        """Missing associated documentation comment in .proto file"""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_HelloServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'hello_world': grpc.unary_unary_rpc_method_handler(
                    servicer.hello_world,
                    request_deserializer=example__pb2.HelloRequest.FromString,
                    response_serializer=example__pb2.HelloResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'HelloService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class HelloService(object):
    """Missing associated documentation comment in .proto file"""

    @staticmethod
    def hello_world(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/HelloService/hello_world',
            example__pb2.HelloRequest.SerializeToString,
            example__pb2.HelloResponse.FromString,
            options, channel_credentials,
            call_credentials, compression, wait_for_ready, timeout, metadata)
