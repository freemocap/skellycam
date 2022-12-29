import logging

LOG_FILE = "log\synchronizer.log"
LOG_LEVEL = logging.DEBUG
LOG_FORMAT = " %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s"

logging.basicConfig(filename=LOG_FILE, filemode="w", format=LOG_FORMAT, level=LOG_LEVEL)

from skellycam.detection.models.frame_payload import FramePayload
import sys
import time
from pathlib import Path
from queue import Queue
from threading import Thread, Event

import cv2
import numpy as np

class Synchronizer:
    def __init__(self, ports):
        # self.streams = streams
        self.current_bundle = None

        self.notice_subscribers = []  # queues that will be notified of new bundles
        self.bundle_subscribers = []    # queues that will receive actual frame data
        
        self.frame_data = {}
        self.stop_event = Event()

        self.ports = ports

        self.initialize_ledgers()
        self.spin_up() 

    def stop(self):
        self.stop_event.set()
        self.bundler.join()
        for t in self.threads:
            t.join()
            
        
    def initialize_ledgers(self):
        # note, these starting values will get overwritten once frames start coming in
        # the first frame number to actually come in will not be zero based on current testing
        self.port_frame_count = {port: 0 for port in self.ports}
        self.port_current_frame = {port: 0 for port in self.ports}
        self.mean_frame_times = []
    
    def spin_up(self):

        logging.info("Starting frame bundler...")
        self.bundler = Thread(target=self.bundle_frames, args=(), daemon=True)
        self.bundler.start()
        
    def subscribe_to_bundle(self, q):
        # subscribers are notified via the queue that a new frame bundle is available
        # this is intended to avoid issues with latency due to multiple iterations
        # of frames being passed from one queue to another
        logging.info("Adding queue to receive notice of bundle update")
        self.notice_subscribers.append(q)

    def subscribe_to_bundle(self, q):
        logging.info("Adding queue to receive frame bundle")
        self.bundle_subscribers.append(q)

    def release_bundle_q(self,q):
        logging.info("Releasing record queue")
        self.bundle_subscribers.remove(q)


    def add_frame_payload(self, payload:FramePayload):
        
        # once frames actually start coming in, need to set it to the correct
        # starting point    
        if self.port_current_frame[payload.camera_id] == 0:
            self.port_current_frame[payload.camera_id] = payload.frame_number
            self.port_frame_count[payload.camera_id] = payload.frame_number
            
        print(f"{payload.camera_id}: {payload.frame_number} @ {payload.timestamp_ns/(10^9)}")
        key = f"{payload.camera_id}_{payload.frame_number}"
        self.frame_data[key] = {
            "port": payload.camera_id,
            "frame": payload.image,
            "frame_index": self.port_frame_count[payload.camera_id],
            "frame_time": payload.timestamp_ns,
        }
        
        self.port_frame_count[payload.camera_id] += 1

    # get minimum value of frame_time for next layer
    def earliest_next_frame(self, port):
        """Looks at next unassigned frame across the ports to determine
        the earliest time at which each of them was read"""
        times_of_next_frames = []
        for p in self.ports:
            next_index = self.port_current_frame[p] + 1
            frame_data_key =  f"{p}_{next_index}"
            
            # problem with outpacing the threads reading data in, so wait if need be
            while frame_data_key not in self.frame_data.keys():
                logging.debug(f"Waiting in a loop for frame data to populate with key: {frame_data_key}")
                time.sleep(.001)

            next_frame_time = self.frame_data[frame_data_key]["frame_time"]
            if p != port:
                times_of_next_frames.append(next_frame_time)

        return min(times_of_next_frames)
    
    def latest_current_frame(self, port):
        """Provides the latest frame_time of the current frames not inclusive of the provided port """
        times_of_current_frames = []
        for p in self.ports:
            current_index = self.port_current_frame[p]
            current_frame_time = self.frame_data[f"{p}_{current_index}"]["frame_time"]
            if p != port:
                times_of_current_frames.append(current_frame_time)
                
        return max(times_of_current_frames)
    
    def frame_slack(self):
        """Determine how many unassigned frames are sitting in self.dataframe"""

        slack = [
            self.port_frame_count[port] - self.port_current_frame[port]
            for port in self.ports
        ]
        logging.debug(f"Slack in frames is {slack}")
        return min(slack)

    def average_fps(self):
        """"""
        # only look at the most recent layers
        if len(self.mean_frame_times) > 10:
            self.mean_frame_times = self.mean_frame_times[-10:]

        delta_t = np.diff(self.mean_frame_times)
        mean_delta_t = np.mean(delta_t)

        return 1 / mean_delta_t

    def bundle_frames(self):

        logging.info("About to start bundling frames...")
        while not self.stop_event.is_set():

            # need to wait for data to populate before synchronization can begin
            while self.frame_slack() < 2:
                time.sleep(.01)

            next_layer = {}
            layer_frame_times = []
            
            # build earliest next/latest current dictionaries for each port to determine where to put frames           
            # must be done before going in and making any updates to the frame index
            earliest_next = {}
            latest_current = {}
            

            for port in self.ports:
                earliest_next[port] = self.earliest_next_frame(port)
                latest_current[port] = self.latest_current_frame(port)
                current_frame_index = self.port_current_frame[port]
                
                
            for port in self.ports:
                current_frame_index = self.port_current_frame[port]

                port_index_key = f"{port}_{current_frame_index}"
                current_frame_data = self.frame_data[port_index_key]
                frame_time = current_frame_data["frame_time"]

                # don't put a frame in a bundle if the next bundle has a frame before it
                if frame_time > earliest_next[port]:
                    # definitly should be put in the next layer and not this one
                    next_layer[port] = None
                    logging.warning(f"Skipped frame at port {port}: > earliest_next")
                elif earliest_next[port] - frame_time < frame_time-latest_current[port]: # frame time is closer to earliest next than latest current
                    # if it's closer to the earliest next frame than the latest current frame, bump it up
                    # only applying for 2 camera setup where I noticed this was an issue (frames stay out of synch)
                    next_layer[port] = None
                    logging.warning(f"Skipped frame at port {port}: delta < time-latest_current")
                else:
                    # add the data and increment the index
                    next_layer[port] = self.frame_data.pop(port_index_key)
                    self.port_current_frame[port] += 1
                    layer_frame_times.append(frame_time)
                    logging.debug(f"Adding to layer from port {port} at index {current_frame_index} and frame time: {frame_time}")
                    
            logging.debug(f"Unassigned Frames: {len(self.frame_data)}")

            self.mean_frame_times.append(np.mean(layer_frame_times))

            self.current_bundle = next_layer
            # notify other processes that the current bundle is ready for processing
            # only for tasks that can risk missing a frame bundle
            for q in self.notice_subscribers:
                logging.debug(f"Giving notice of new bundle via {q}")
                q.put("new bundle available")

            for q in self.bundle_subscribers:
                logging.debug(f"Placing new bundle on queue: {q}")
                logging.debug("Placing bundle on subscribers queue")
                q.put(self.current_bundle)

            self.fps = self.average_fps()

        logging.info("Frame bundler successfully ended")
