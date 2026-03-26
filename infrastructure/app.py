#!/usr/bin/env python3
import aws_cdk as cdk
from capacity_block_async_stack import CapacityBlockAsyncStack

app = cdk.App()
CapacityBlockAsyncStack(app, "CapacityBlockAsyncStack")

app.synth()
