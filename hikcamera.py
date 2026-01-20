# -- coding: utf-8 --
"""海康相机简洁接口类

Example:
    >>> from hikcamera import HikCamera
    >>> with HikCamera() as camera:
    ...     camera.start()
    ...     image = camera.get_image()  # BGR numpy 数组
    ...     cv2.imshow("image", image)
"""

import sys
import platform
import os
from ctypes import *
from ctypes import memmove
from typing import Optional, Dict, Any


def copy_bytes(source, length):
    """从 ctypes 指针复制字节数据到 bytes 对象"""
    buffer = (c_ubyte * length)()
    memmove(buffer, source, length)
    return bytes(buffer)

# 兼容不同操作系统加载动态库
currentsystem = platform.system()
if currentsystem == 'Windows':
    mvs_path = os.path.join(os.getenv('MVCAM_COMMON_RUNENV'), "Samples", "Python", "MvImport")
else:
    mvs_path = "/opt/MVS/Samples/64/Python/MvImport"

if mvs_path not in sys.path:
    sys.path.append(mvs_path)

import numpy as np
import cv2
from MvCameraControl_class import *

from .utils import (
    decoding_char,
    get_device_info,
    enumerate_devices,
    is_bayer_format,
    is_mono_format,
    is_rgb_format,
    BAYER_TO_COLOR_CODE,
    get_pixel_format_name,
)
from .config import HikCameraConfig, CameraParams


# 全局 SDK 初始化标志
_SDK_INITIALIZED = False
_SDK_INIT_COUNT = 0


class HikCameraError(Exception):
    """海康相机错误异常"""
    pass


class HikCamera:
    """海康相机简洁接口类

    支持连续采集和触发模式，自动处理像素格式转换，
    使用户可以像使用 Realsense 一样简单地使用海康相机。

    Attributes:
        config: 相机配置对象
        is_running: 相机是否正在采集
    """

    def __init__(self, camera_index: int = 0, trigger_mode: str = "continuous",
                 config: Optional[HikCameraConfig] = None):
        """初始化海康相机

        Args:
            camera_index: 设备索引，默认0（第一个设备）
            trigger_mode: 触发模式，"continuous"(连续采集) 或 "trigger"(触发采集)
            config: HikCameraConfig 配置对象，如果为 None 则使用默认配置

        Raises:
            HikCameraError: 没有找到相机或打开失败
        """
        global _SDK_INITIALIZED, _SDK_INIT_COUNT

        # 初始化 SDK（全局唯一）
        if not _SDK_INITIALIZED:
            ret = MvCamera.MV_CC_Initialize()
            if ret != 0:
                raise HikCameraError(f"SDK 初始化失败! ret[0x{ret:x}]")
            _SDK_INITIALIZED = True
        _SDK_INIT_COUNT += 1

        self._cam = MvCamera()
        self._config = config or HikCameraConfig(
            camera_index=camera_index,
            trigger_mode=trigger_mode
        )
        self._is_running = False
        self._device_info: Optional[Dict[str, Any]] = None
        self._pixel_type = None
        self._nPayloadSize = 0

        # 自动连接
        self._auto_connect()

    def _auto_connect(self) -> None:
        """自动连接相机"""
        # 重新枚举设备，获取原始 deviceList
        deviceList = MV_CC_DEVICE_INFO_LIST()
        tlayerType = (MV_GIGE_DEVICE | MV_USB_DEVICE | MV_GENTL_CAMERALINK_DEVICE
                      | MV_GENTL_CXP_DEVICE | MV_GENTL_XOF_DEVICE)

        ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
        if ret != 0:
            raise HikCameraError(f"枚举设备失败! ret[0x{ret:x}]")

        if deviceList.nDeviceNum == 0:
            raise HikCameraError("未找到可用的海康相机设备")

        idx = self._config.camera_index
        if idx >= deviceList.nDeviceNum:
            raise HikCameraError(f"设备索引 {idx} 超出范围，共有 {deviceList.nDeviceNum} 个设备")

        # 获取设备信息
        mvcc_dev_info = cast(
            deviceList.pDeviceInfo[idx],
            POINTER(MV_CC_DEVICE_INFO)
        ).contents

        # 保存设备信息
        self._device_info = get_device_info(mvcc_dev_info)

        # 创建设备句柄
        ret = self._cam.MV_CC_CreateHandle(mvcc_dev_info)
        if ret != 0:
            raise HikCameraError(f"创建句柄失败! ret[0x{ret:x}]")

        # 打开设备
        ret = self._cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
        if ret != 0:
            self._cam.MV_CC_DestroyHandle()
            raise HikCameraError(f"打开设备失败! ret[0x{ret:x}]")

        # GigE 相机优化包大小
        if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
            nPacketSize = self._cam.MV_CC_GetOptimalPacketSize()
            if int(nPacketSize) > 0:
                self._cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)

        # 设置触发模式
        if self._config.trigger_mode == "trigger":
            self._cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_ON)
            # 设置触发源为软件触发
            self._cam.MV_CC_SetEnumValue("TriggerSource", MV_TRIGGER_SOURCE_SOFTWARE)
        else:
            self._cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)

        # 获取有效载荷大小
        stParam = MVCC_INTVALUE()
        ret = self._cam.MV_CC_GetIntValue("PayloadSize", stParam)
        if ret != 0:
            raise HikCameraError(f"获取 PayloadSize 失败! ret[0x{ret:x}]")
        self._nPayloadSize = stParam.nCurValue

    def start(self) -> None:
        """开始采集"""
        if self._is_running:
            return

        ret = self._cam.MV_CC_StartGrabbing()
        if ret != 0:
            raise HikCameraError(f"开始采集失败! ret[0x{ret:x}]")
        self._is_running = True

    def stop(self) -> None:
        """停止采集"""
        if not self._is_running:
            return

        ret = self._cam.MV_CC_StopGrabbing()
        if ret != 0:
            raise HikCameraError(f"停止采集失败! ret[0x{ret:x}]")
        self._is_running = False

    def get_image(self, timeout: Optional[int] = None) -> np.ndarray:
        """获取一帧图像（连续采集模式下获取最新帧）

        Args:
            timeout: 超时时间（毫秒），默认使用配置中的值

        Returns:
            BGR 格式的 numpy 数组

        Raises:
            HikCameraError: 获取图像失败或超时
        """
        if not self._is_running:
            raise HikCameraError("相机未开始采集，请先调用 start()")

        timeout = timeout or self._config.timeout

        stOutFrame = MV_FRAME_OUT()
        memset(byref(stOutFrame), 0, sizeof(stOutFrame))

        ret = self._cam.MV_CC_GetImageBuffer(stOutFrame, timeout)
        if None == stOutFrame.pBufAddr or ret != 0:
            raise HikCameraError(f"获取图像失败! ret[0x{ret:x}]")

        try:
            # 转换图像数据
            image = self._convert_frame_to_bgr(stOutFrame)
        finally:
            self._cam.MV_CC_FreeImageBuffer(stOutFrame)

        return image

    def trigger_and_get_image(self, timeout: Optional[int] = None) -> np.ndarray:
        """触发一次并获取图像（触发模式下使用）

        Args:
            timeout: 超时时间（毫秒），默认使用配置中的值

        Returns:
            BGR 格式的 numpy 数组

        Raises:
            HikCameraError: 获取图像失败或超时
        """
        if self._config.trigger_mode != "trigger":
            raise HikCameraError("trigger_and_get_image 只能在触发模式下使用")

        # 触发一次
        ret = self._cam.MV_CC_SetCommandValue("TriggerSoftware")
        if ret != 0:
            raise HikCameraError(f"触发失败! ret[0x{ret:x}]")

        return self.get_image(timeout)

    def _convert_frame_to_bgr(self, stOutFrame: MV_FRAME_OUT) -> np.ndarray:
        """将帧数据转换为 BGR 格式的 numpy 数组

        Args:
            stOutFrame: 帧数据

        Returns:
            BGR 格式的 numpy 数组
        """
        width = stOutFrame.stFrameInfo.nWidth
        height = stOutFrame.stFrameInfo.nHeight
        pixel_type = stOutFrame.stFrameInfo.enPixelType
        frame_len = stOutFrame.stFrameInfo.nFrameLen
        self._pixel_type = pixel_type

        # 获取图像数据地址
        if stOutFrame.pBufAddr is None:
            raise HikCameraError("图像缓冲区地址为空")

        # 从 ctypes 指针复制数据到 numpy 数组
        pData = stOutFrame.pBufAddr
        image_array = np.frombuffer(copy_bytes(pData, frame_len), dtype=np.uint8)

        # 根据像素格式转换
        if is_rgb_format(pixel_type):
            # RGB/BGR 格式直接转换
            if pixel_type == PixelType_Gvsp_RGB8_Packed:
                # RGB -> BGR
                image = image_array.reshape((height, width, 3))
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            elif pixel_type == PixelType_Gvsp_BGR8_Packed:
                # BGR 直接使用
                image = image_array.reshape((height, width, 3))
            else:
                # RGBA/BGRA -> BGR
                image = image_array.reshape((height, width, 4))
                if pixel_type == PixelType_Gvsp_RGBA8_Packed:
                    image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
                else:
                    image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

        elif is_bayer_format(pixel_type):
            # Bayer 格式转换为 BGR
            color_code = BAYER_TO_COLOR_CODE.get(pixel_type, 0)
            image = image_array.reshape((height, width))

            if color_code == 0:  # BayerGR
                image = cv2.cvtColor(image, cv2.COLOR_BAYER_GR2BGR)
            elif color_code == 1:  # BayerRG
                image = cv2.cvtColor(image, cv2.COLOR_BAYER_RG2BGR)
            elif color_code == 2:  # BayerGB
                image = cv2.cvtColor(image, cv2.COLOR_BAYER_GB2BGR)
            else:  # BayerBG
                image = cv2.cvtColor(image, cv2.COLOR_BAYER_BG2BGR)

        elif is_mono_format(pixel_type):
            # 单色格式直接使用，转换为 3 通道
            image = image_array.reshape((height, width))
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        else:
            raise HikCameraError(
                f"不支持的像素格式: {get_pixel_format_name(pixel_type)}"
            )

        return image

    def close(self) -> None:
        """关闭相机，释放资源"""
        global _SDK_INITIALIZED, _SDK_INIT_COUNT

        if self._is_running:
            self.stop()

        if self._cam is not None:
            try:
                self._cam.MV_CC_CloseDevice()
                self._cam.MV_CC_DestroyHandle()
            except:
                pass
            self._cam = None

        # 反初始化 SDK（全局唯一）
        _SDK_INIT_COUNT -= 1
        if _SDK_INIT_COUNT <= 0:
            MvCamera.MV_CC_Finalize()
            _SDK_INITIALIZED = False

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()
        return False

    def __del__(self):
        """析构函数"""
        try:
            self.close()
        except:
            pass

    # ============ 属性 ============

    @property
    def width(self) -> int:
        """获取图像宽度"""
        return self._config.width

    @width.setter
    def width(self, value: int) -> None:
        """设置图像宽度"""
        self._config.width = value
        ret = self._cam.MV_CC_SetIntValue("Width", value)
        if ret != 0:
            raise HikCameraError(f"设置 Width 失败! ret[0x{ret:x}]")

    @property
    def height(self) -> int:
        """获取图像高度"""
        return self._config.height

    @height.setter
    def height(self, value: int) -> None:
        """设置图像高度"""
        self._config.height = value
        ret = self._cam.MV_CC_SetIntValue("Height", value)
        if ret != 0:
            raise HikCameraError(f"设置 Height 失败! ret[0x{ret:x}]")

    @property
    def exposure(self) -> int:
        """获取曝光时间（微秒）"""
        # 尝试使用 FloatValue 获取（某些相机使用浮点型）
        stFloatParam = MVCC_FLOATVALUE()
        ret = self._cam.MV_CC_GetFloatValue("ExposureTime", stFloatParam)
        if ret == 0:
            return int(stFloatParam.fCurValue)

        # 尝试使用 IntValue 获取
        stIntParam = MVCC_INTVALUE()
        ret = self._cam.MV_CC_GetIntValue("ExposureTime", stIntParam)
        if ret == 0:
            return stIntParam.nCurValue

        raise HikCameraError(f"获取 ExposureTime 失败! ret[0x{ret:x}]")

    @exposure.setter
    def exposure(self, value: int) -> None:
        """设置曝光时间（微秒）"""
        self._config.exposure = value
        # 使用浮点型设置（大多数相机支持）
        ret = self._cam.MV_CC_SetFloatValue("ExposureTime", float(value))
        if ret != 0:
            # 尝试使用整型设置
            ret = self._cam.MV_CC_SetIntValue("ExposureTime", value)
        if ret != 0:
            raise HikCameraError(f"设置 ExposureTime 失败! ret[0x{ret:x}]")

    @property
    def gain(self) -> float:
        """获取增益"""
        stParam = MVCC_FLOATVALUE()
        ret = self._cam.MV_CC_GetFloatValue("Gain", stParam)
        if ret != 0:
            raise HikCameraError(f"获取 Gain 失败! ret[0x{ret:x}]")
        return stParam.fCurValue

    @gain.setter
    def gain(self, value: float) -> None:
        """设置增益"""
        self._config.gain = value
        # 尝试使用 "Gain" 参数
        ret = self._cam.MV_CC_SetFloatValue("Gain", value)
        if ret != 0:
            # 尝试使用 "AnalogGain" 参数
            ret = self._cam.MV_CC_SetFloatValue("AnalogGain", value)
        if ret != 0:
            print(f"警告: 设置增益失败 (ret=0x{ret:x})，增益可能不受支持")
            # 不抛出异常，只是警告

    @property
    def fps(self) -> float:
        """获取帧率"""
        stParam = MVCC_FLOATVALUE()
        ret = self._cam.MV_CC_GetFloatValue("AcquisitionFrameRate", stParam)
        if ret != 0:
            raise HikCameraError(f"获取 AcquisitionFrameRate 失败! ret[0x{ret:x}]")
        return stParam.fCurValue

    @fps.setter
    def fps(self, value: float) -> None:
        """设置帧率"""
        self._config.fps = int(value)
        ret = self._cam.MV_CC_SetFloatValue("AcquisitionFrameRate", value)
        if ret != 0:
            raise HikCameraError(f"设置 AcquisitionFrameRate 失败! ret[0x{ret:x}]")

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        """获取设备信息"""
        return self._device_info

    @property
    def is_running(self) -> bool:
        """相机是否正在采集"""
        return self._is_running

    @property
    def pixel_type(self) -> Optional[int]:
        """获取当前像素格式"""
        return self._pixel_type

    @property
    def trigger_mode(self) -> str:
        """获取触发模式"""
        return self._config.trigger_mode

    # ============ 参数查询与设置 ============

    def get_params(self) -> CameraParams:
        """获取相机关键参数

        Returns:
            CameraParams 对象，包含所有关键参数
        """
        # 获取当前像素格式名称
        pixel_format_name = get_pixel_format_name(self._pixel_type) if self._pixel_type else "Unknown"

        # 获取实际参数值
        params = CameraParams(
            width=self.width,
            height=self.height,
            exposure=self._get_exposure(),
            gain=self._get_gain(),
            fps=self._get_fps(),
            pixel_format=pixel_format_name,
            trigger_mode=self.trigger_mode,
            offset_x=self._get_offset_x(),
            offset_y=self._get_offset_y(),
        )

        return params

    def set_params(self, width: Optional[int] = None, height: Optional[int] = None,
                   exposure: Optional[float] = None, gain: Optional[float] = None,
                   fps: Optional[float] = None, trigger_mode: Optional[str] = None,
                   offset_x: Optional[int] = None, offset_y: Optional[int] = None) -> None:
        """设置相机参数

        Args:
            width: 图像宽度（像素）
            height: 图像高度（像素）
            exposure: 曝光时间（微秒）
            gain: 增益
            fps: 采集帧率
            trigger_mode: 触发模式 ("continuous" 或 "trigger")
            offset_x: 水平偏移
            offset_y: 垂直偏移

        Raises:
            HikCameraError: 设置参数失败
        """
        if width is not None:
            self.width = width

        if height is not None:
            self.height = height

        if exposure is not None:
            self.exposure = exposure

        if gain is not None:
            self.gain = gain

        if fps is not None:
            self.fps = fps

        if trigger_mode is not None:
            if trigger_mode not in ("continuous", "trigger"):
                raise HikCameraError(f"无效的触发模式: {trigger_mode}")
            self._config.trigger_mode = trigger_mode
            # 实时更新触发模式
            if trigger_mode == "trigger":
                self._cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_ON)
                self._cam.MV_CC_SetEnumValue("TriggerSource", MV_TRIGGER_SOURCE_SOFTWARE)
            else:
                self._cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)

        if offset_x is not None:
            self._set_offset_x(offset_x)

        if offset_y is not None:
            self._set_offset_y(offset_y)

    def _get_exposure(self) -> float:
        """获取曝光时间"""
        stFloatParam = MVCC_FLOATVALUE()
        ret = self._cam.MV_CC_GetFloatValue("ExposureTime", stFloatParam)
        if ret == 0:
            return stFloatParam.fCurValue

        stIntParam = MVCC_INTVALUE()
        ret = self._cam.MV_CC_GetIntValue("ExposureTime", stIntParam)
        if ret == 0:
            return float(stIntParam.nCurValue)
        return 0.0

    def _get_gain(self) -> float:
        """获取增益"""
        stParam = MVCC_FLOATVALUE()
        ret = self._cam.MV_CC_GetFloatValue("Gain", stParam)
        if ret == 0:
            return stParam.fCurValue
        return 0.0

    def _get_fps(self) -> float:
        """获取帧率"""
        stParam = MVCC_FLOATVALUE()
        ret = self._cam.MV_CC_GetFloatValue("AcquisitionFrameRate", stParam)
        if ret == 0:
            return stParam.fCurValue
        return 0.0

    def _get_offset_x(self) -> int:
        """获取水平偏移"""
        stParam = MVCC_INTVALUE()
        ret = self._cam.MV_CC_GetIntValue("OffsetX", stParam)
        if ret == 0:
            return stParam.nCurValue
        return 0

    def _get_offset_y(self) -> int:
        """获取垂直偏移"""
        stParam = MVCC_INTVALUE()
        ret = self._cam.MV_CC_GetIntValue("OffsetY", stParam)
        if ret == 0:
            return stParam.nCurValue
        return 0

    def _set_offset_x(self, value: int) -> None:
        """设置水平偏移"""
        ret = self._cam.MV_CC_SetIntValue("OffsetX", value)
        if ret != 0:
            raise HikCameraError(f"设置 OffsetX 失败! ret[0x{ret:x}]")

    def _set_offset_y(self, value: int) -> None:
        """设置垂直偏移"""
        ret = self._cam.MV_CC_SetIntValue("OffsetY", value)
        if ret != 0:
            raise HikCameraError(f"设置 OffsetY 失败! ret[0x{ret:x}]")

    # ============ 静态方法 ============

    @staticmethod
    def list_devices() -> list:
        """列出所有可用的设备

        Returns:
            设备信息字典列表
        """
        return enumerate_devices()


def device_list() -> list:
    """列出所有可用的海康相机设备（快捷函数）"""
    return enumerate_devices()
