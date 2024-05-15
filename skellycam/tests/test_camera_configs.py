import pytest

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.camera_configs import CameraConfigs


def test_camera_configs_default():
    camera_configs = CameraConfigs()
    assert camera_configs[0] == CameraConfig(camera_id=CameraId(0))



def test_camera_configs_str():
    camera_configs = CameraConfigs()
    assert "COMPUTED" in str(camera_configs)


def test_camera_configs_getitem():
    camera_configs = CameraConfigs()
    assert camera_configs[0] == CameraConfig(camera_id=CameraId(0))


def test_camera_configs_setitem_single():
    camera_configs = CameraConfigs()
    new_config = CameraConfig(camera_id=CameraId(1))
    camera_configs[1] = new_config
    assert camera_configs[1] == new_config


def test_camera_configs_delitem():
    camera_configs = CameraConfigs()
    del camera_configs[0]
    with pytest.raises(KeyError):
        _ = camera_configs[0]


def test_camera_configs_iter():
    camera_configs = CameraConfigs()
    assert list(camera_configs) == [CameraId(0)]


def test_camera_configs_len():
    camera_configs = CameraConfigs()
    assert len(camera_configs) == 1


def test_camera_configs_contains():
    camera_configs = CameraConfigs()
    assert CameraId(0) in camera_configs


def test_camera_configs_eq():
    camera_configs1 = CameraConfigs()
    camera_configs2 = CameraConfigs()
    assert camera_configs1 == camera_configs2


def test_camera_configs_keys():
    camera_configs = CameraConfigs()
    assert list(camera_configs.keys()) == [CameraId(0)]


def test_camera_configs_values():
    camera_configs = CameraConfigs()
    assert list(camera_configs.values()) == [CameraConfig(camera_id=CameraId(0))]


def test_camera_configs_items():
    camera_configs = CameraConfigs()
    assert list(camera_configs.items()) == [(CameraId(0), CameraConfig(camera_id=CameraId(0)))]
