import asyncio
import time


def wait_1s(wait_loop_time: float = 1.0):
    time.sleep(wait_loop_time)


def wait_10ms(wait_loop_time: float = 1e-2):
    time.sleep(wait_loop_time)


def wait_1ms(wait_loop_time: float = 1e-3):
    time.sleep(wait_loop_time)


def wait_1us(wait_loop_time: float = 1e-6):
    # microseconds (the `u` is a stand in for the Greek letter μ (mu), which is the symbol for micro)
    time.sleep(wait_loop_time)


async def async_wait_1_sec(wait_loop_time: float = 1.0):
    await asyncio.sleep(wait_loop_time)


async def async_wait_10ms(wait_loop_time: float = 1e-2):
    await asyncio.sleep(wait_loop_time)


async def async_wait_1ms(wait_loop_time: float = 1e-3):
    await asyncio.sleep(wait_loop_time)


async def async_wait_1us(wait_loop_time: float = 1e-6):
    await asyncio.sleep(wait_loop_time)
