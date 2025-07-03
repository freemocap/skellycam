import cv2
from cv2.videoio_registry import getBackendName
from cv2_enumerate_cameras import supported_backends, enumerate_cameras
from cv2_enumerate_cameras.camera_info import CameraInfo
from pydantic import BaseModel

from skellycam.core.types.type_overloads import CameraIndexInt, CameraNameString, CameraBackendInt, CameraVendorIdInt, \
    CameraProductIdInt, CameraDevicePathString, CameraBackendNameString


# define a function to search for a camera
def find_camera(
        index: CameraIndexInt | None = None,
        vid: CameraVendorIdInt | None = None,
        pid: CameraProductIdInt | None = None,
        path: CameraDevicePathString | None = None,
        api_preference: CameraBackendInt = cv2.CAP_ANY):
    for i in enumerate_cameras(api_preference):
        if index is not None and i.index == index:
            return cv2.VideoCapture(i.index, i.backend)
        if path is not None and i.path == path:
            return cv2.VideoCapture(i.index, i.backend)
        if vid is not None and pid is not None and i.vid == vid and i.pid == pid:
            return cv2.VideoCapture(i.index, i.backend)
    return None


class CameraDeviceInfo(BaseModel):
    index: CameraIndexInt
    name: CameraNameString
    vid: CameraVendorIdInt | None = None
    pid: CameraProductIdInt | None = None
    path: CameraDevicePathString | None = None
    backend_id: CameraBackendInt | None = None
    backend_name: CameraBackendNameString | None = None

    @classmethod
    def from_camera_info(cls, camera_info: CameraInfo) -> 'CameraDeviceInfo':
        return cls(
            index=camera_info.index,
            name=camera_info.name,
            vid=camera_info.vid,
            pid=camera_info.pid,
            path=camera_info.path,
            backend_id=camera_info.backend,
            backend_name=getBackendName(camera_info.backend)
        )
    def create_cv2_video_capture(self) -> 'cv2.VideoCapture':
        cap = find_camera(
            vid=self.vid,
            pid=self.pid,
            path=self.path,
            api_preference=self.backend_id if self.backend_id is not None else cv2.CAP_ANY
        )
        if not cap.isOpened():
            raise Exception(f"Failed to open camera {self.index} with VID: {self.vid} and PID: {self.pid}")
        # Attempt to read a frame to ensure the camera is working
        success, image = cap.read()

        if not success or image is None:
            cap.release()
            raise Exception(f"Failed to read frame from camera {self.index} with VID: {self.vid} and PID: {self.pid}")
        return cap


class CameraDevices(BaseModel):
    cameras_by_backend: dict[CameraBackendInt, list[CameraDeviceInfo]]

    @classmethod
    def detect_available_cameras(cls, backend: CameraBackendInt | None=None, filter_virtual:bool=True) -> 'CameraDevices':
        """
        Detects available cameras using the cv2_enumerate_cameras package.
        Returns a list of CameraInfo objects for each detected camera.
        """

        available_backends = supported_backends if backend is None else [backend]
        cameras_by_backend = {backend: [] for backend in available_backends}
        for backend in available_backends:
            for camera_info in enumerate_cameras(backend):
                if filter_virtual and 'virtual' in camera_info.name.lower():
                    continue
                if camera_info.vid is None or camera_info.pid is None:
                    if 'facetime' not in camera_info.name.lower():
                        # Skip cameras without VID and PID (unless its a 'facetime' camera on macOS)
                        continue

                cameras_by_backend[backend].append(CameraDeviceInfo.from_camera_info(camera_info))
        return cls(
            cameras_by_backend=cameras_by_backend
        )

    def get_cameras_by_backend(self, backend: CameraBackendInt | None = None) -> list[CameraDeviceInfo]:
        """
        Returns a list of DetectedCamera objects for the specified backend.
        """
        if backend is None or backend == cv2.CAP_ANY:
            return [camera for cameras in self.cameras_by_backend.values() for camera in cameras]
        return self.cameras_by_backend.get(backend, [])


if __name__ == "__main__":

    # Example usage
    cameras = CameraDevices.detect_available_cameras(backend=cv2.CAP_DSHOW, filter_virtual=True)
    for backend, camera_list in cameras.cameras_by_backend.items():
        print(f"Backend: {getBackendName(backend)}")
        for camera in camera_list:
            print(f"  {camera.index}: {camera.name} (VID: {camera.vid}, PID: {camera.pid}, Path: {camera.path})")