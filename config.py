# -- coding: utf-8 --
"""海康相机配置类"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class CameraParams:
    """相机参数类 - 用于查询和设置相机关键参数

    Attributes:
        width: 图像宽度（像素）
        height: 图像高度（像素）
        exposure: 曝光时间（微秒）
        gain: 增益
        fps: 采集帧率
        pixel_format: 像素格式
        trigger_mode: 触发模式
        offset_x: 水平偏移
        offset_y: 垂直偏移
    """
    width: int = 0
    height: int = 0
    exposure: float = 0.0
    gain: float = 0.0
    fps: float = 0.0
    pixel_format: str = ""
    trigger_mode: str = "continuous"
    offset_x: int = 0
    offset_y: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'width': self.width,
            'height': self.height,
            'exposure': self.exposure,
            'gain': self.gain,
            'fps': self.fps,
            'pixel_format': self.pixel_format,
            'trigger_mode': self.trigger_mode,
            'offset_x': self.offset_x,
            'offset_y': self.offset_y,
        }

    def __repr__(self) -> str:
        """友好字符串表示"""
        params = ', '.join([f"{k}={v}" for k, v in self.to_dict().items()])
        return f"CameraParams({params})"


@dataclass
class HikCameraConfig:
    """海康相机配置类

    Attributes:
        camera_index: 设备索引，默认0（第一个设备）
        trigger_mode: 触发模式，"continuous"(连续采集) 或 "trigger"(触发采集)
        width: 图像宽度
        height: 图像高度
        exposure: 曝光时间（微秒）
        gain: 增益
        fps: 帧率
        timeout: 获取图像超时时间（毫秒）
    """
    camera_index: int = 0
    trigger_mode: str = "continuous"
    width: int = 1280
    height: int = 720
    exposure: int = 10000
    gain: float = 0.0
    fps: int = 30
    timeout: int = 1000

    def __post_init__(self):
        """验证配置参数"""
        if self.trigger_mode not in ("continuous", "trigger"):
            raise ValueError(f"Invalid trigger_mode: {self.trigger_mode}. "
                           f"Must be 'continuous' or 'trigger'")
        if self.camera_index < 0:
            raise ValueError(f"camera_index must be non-negative, got {self.camera_index}")
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"width and height must be positive")
        if self.exposure < 0:
            raise ValueError(f"exposure must be non-negative")
        if self.gain < 0:
            raise ValueError(f"gain must be non-negative")
        if self.fps <= 0:
            raise ValueError(f"fps must be positive")
        if self.timeout <= 0:
            raise ValueError(f"timeout must be positive")
