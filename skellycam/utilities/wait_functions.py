import asyncio
import time


def wait_1s():
    time.sleep(1.0)


def wait_10ms():
    time.sleep(1e-2)


def wait_1ms():
    time.sleep(1e-3)


def wait_10us():
    # microseconds (the `u` is a stand in for the Greek letter μ (mu), which is the symbol for micro)
    time.sleep(1e-5)

def wait_1us():
    # microseconds (the `u` is a stand in for the Greek letter μ (mu), which is the symbol for micro)
    time.sleep(1e-5)


async def async_wait_1_sec():
    await asyncio.sleep(1.0)


async def async_wait_10ms():
    await asyncio.sleep(1e-2)


async def async_wait_1ms():
    await asyncio.sleep(1e-3)


async def async_wait_10us():
    await asyncio.sleep(1e-5)

async def async_wait_1us():
    await asyncio.sleep(1e-6)
