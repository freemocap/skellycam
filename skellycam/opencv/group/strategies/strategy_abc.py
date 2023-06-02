from abc import ABC, abstractmethod


class StrategyABC(ABC):
    @abstractmethod
    def start_capture(self):
        """
        Begin capturing frames.
        This function should not return until all cameras
        are ready and capturing.
        """
        raise NotImplementedError()

    @abstractmethod
    def stop_capture(self):
        """
        Stop capturing frames.

        This function should not return until all cameras are stopped and cleaned up.
        """
        raise NotImplementedError()

    @abstractmethod
    def start_recording(self):
        """
        Start saving frames (usually to save to video via some method or another)

        """
        raise NotImplementedError()

    @abstractmethod
    def stop_recording(self):
        """
        Stop saving frames
        """
        raise NotImplementedError()


    @property
    @abstractmethod
    def is_recording(self):
        """
        Returns True if the strategy is currently recording frames.
        """
        raise NotImplementedError()


    @property
    @abstractmethod
    def is_capturing(self):
        raise NotImplementedError()


    @property
    @abstractmethod
    def latest_frames(self):
        """
        Grab the latest frame, usually for viewing.
        """
        raise NotImplementedError()

    @abstractmethod
    def latest_frames_by_camera_id(self, camera_id: str):
        """
        Grab the latest frame, usually for viewing.

        This should be a function optimized for grabbing the frame related
        to the camera.
        """
        raise NotImplementedError()

    @property
    @abstractmethod
    def known_frames_by_camera(self):
        """"""
        raise NotImplementedError()



