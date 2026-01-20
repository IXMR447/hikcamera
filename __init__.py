# -- coding: utf-8 --
"""海康相机模块

提供简洁易用的海康相机接口，支持连续采集和触发模式。

Example:
    >>> from hikcamera import HikCamera
    >>> with HikCamera() as camera:
    ...     camera.start()
    ...     image = camera.get_image()  # BGR numpy 数组
    ...     print(f"图像形状: {image.shape}")
"""

from .hikcamera import (
    HikCamera,
    HikCameraError,
    device_list,
)
from .config import HikCameraConfig, CameraParams
from .utils import (
    enumerate_devices,
    decoding_char,
)

__all__ = [
    'HikCamera',
    'HikCameraError',
    'HikCameraConfig',
    'CameraParams',
    'device_list',
    'enumerate_devices',
    'decoding_char',
]

__version__ = '1.0.0'
