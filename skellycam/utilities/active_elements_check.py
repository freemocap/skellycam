import asyncio
import multiprocessing
import os
import threading
import time

import logging
logger = logging.getLogger(__name__)
from tabulate import tabulate

def check_active_processes():
    print("\nActive Processes:")
    for process in multiprocessing.active_children():
        print(f'Process Name: {process.name}, PID: {process.pid}')


def check_active_threads():
    print("\nActive Threads:")
    for thread in threading.enumerate():
        print(f'Thread Name: {thread.name}, ID: {thread.ident}')


async def check_active_asyncio_tasks():
    print("\nActive Asyncio Tasks:")
    for task in asyncio.all_tasks():
        print(f'Task: {task.get_name()}, Done: {task.done()}, Canceled: {task.cancelled()}')



async def gather_all_active_info():
    active_info = []
    main_process = multiprocessing.current_process()
    active_info.append({"Type": "Process", "Name": main_process.name, "ID": main_process.pid})

    # Gather active processes
    for process in multiprocessing.active_children():
        active_info.append({"Type": "Process", "Name": process.name, "ID": process.pid})
    active_info.append({"Type": "--", "Name": '--', "ID": '--'})
    # Gather active threads
    for thread in threading.enumerate():
        active_info.append({"Type": "Thread", "Name": thread.name, "ID": thread.ident})
    active_info.append({"Type": "--", "Name": '--', "ID": '--'})
    # Gather active asyncio tasks
    for task in asyncio.all_tasks():
        if not task.done():
            active_info.append({"Type": "Asyncio Task", "Name": task.get_name(), "ID": "N/A"})

    return active_info

async def active_elements_check_loop(global_kill_flag: multiprocessing.Value, context: str):
    print("Starting app lifecycle check loop")
    process_check_clock_time = 5
    counter = 0
    active_info = None

    while not global_kill_flag.value:
        time.sleep(1)
        counter += 1
        if counter % process_check_clock_time == 0:
            active_info = await gather_all_active_info()
            if active_info:
                print(f"\n{context} - Active Elements:")
                print(tabulate(active_info, headers="keys", tablefmt="pretty"))
            else:
                print("\nNo active elements.")

    print("FINAL PRINT Active Elements:")
    if active_info:
        print(tabulate(active_info, headers="keys", tablefmt="pretty"))
    else:
        print("\nNo active elements.")
    logger.info("App lifecycle check loop ended")