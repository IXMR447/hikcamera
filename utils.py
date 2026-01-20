# -- coding: utf-8 --
"""海康相机工具函数"""

import sys
import platform
import os
from ctypes import *
from typing import Optional, Tuple, List

# 兼容不同操作系统加载动态库
currentsystem = platform.system()
if currentsystem == 'Windows':
    mvs_path = os.path.join(os.getenv('MVCAM_COMMON_RUNENV'), "Samples", "Python", "MvImport")
else:
    mvs_path = "/opt/MVS/Samples/64/Python/MvImport"

if mvs_path not in sys.path:
    sys.path.append(mvs_path)

from MvCameraControl_class import *


def decoding_char(ctypes_char_array) -> str:
    """安全地从 ctypes 字符数组中解码出字符串。

    适用于 Python 2.x 和 3.x，以及 32/64 位环境。
    """
    byte_str = memoryview(ctypes_char_array).tobytes()

    # 在第一个空字符处截断
    null_index = byte_str.find(b'\x00')
    if null_index != -1:
        byte_str = byte_str[:null_index]

    # 多编码尝试解码
    for encoding in ['gbk', 'utf-8', 'latin-1']:
        try:
            return byte_str.decode(encoding)
        except UnicodeDecodeError:
            continue

    # 如果所有编码都失败，使用替换策略
    return byte_str.decode('latin-1', errors='replace')


def get_device_type_string(n_tlayer_type: int) -> str:
    """获取设备类型字符串"""
    if n_tlayer_type == MV_GIGE_DEVICE or n_tlayer_type == MV_GENTL_GIGE_DEVICE:
        return "GigE"
    elif n_tlayer_type == MV_USB_DEVICE:
        return "USB3 Vision"
    elif n_tlayer_type == MV_GENTL_CAMERALINK_DEVICE:
        return "CameraLink"
    elif n_tlayer_type == MV_GENTL_CXP_DEVICE:
        return "CoaXPress"
    elif n_tlayer_type == MV_GENTL_XOF_DEVICE:
        return "XoF"
    else:
        return "Unknown"


def get_device_info(mvcc_dev_info) -> dict:
    """从设备信息对象提取设备信息字典

    Args:
        mvcc_dev_info: MV_CC_DEVICE_INFO 对象或指针
    """
    # 如果是指针，获取其内容
    if hasattr(mvcc_dev_info, 'contents'):
        mvcc_dev_info = mvcc_dev_info.contents

    device_type = get_device_type_string(mvcc_dev_info.nTLayerType)

    info = {
        "index": -1,
        "type": device_type,
        "model_name": "",
        "serial_number": "",
        "ip_address": None,
    }

    if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE or mvcc_dev_info.nTLayerType == MV_GENTL_GIGE_DEVICE:
        info["model_name"] = decoding_char(mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName)
        # 解析 IP 地址
        ip = mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp
        info["ip_address"] = f"{(ip >> 24) & 0xFF}.{(ip >> 16) & 0xFF}.{(ip >> 8) & 0xFF}.{ip & 0xFF}"

    elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
        info["model_name"] = decoding_char(mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName)
        info["serial_number"] = decoding_char(mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber)

    elif mvcc_dev_info.nTLayerType == MV_GENTL_CAMERALINK_DEVICE:
        info["model_name"] = decoding_char(mvcc_dev_info.SpecialInfo.stCMLInfo.chModelName)
        info["serial_number"] = decoding_char(mvcc_dev_info.SpecialInfo.stCMLInfo.chSerialNumber)

    elif mvcc_dev_info.nTLayerType == MV_GENTL_CXP_DEVICE:
        info["model_name"] = decoding_char(mvcc_dev_info.SpecialInfo.stCXPInfo.chModelName)
        info["serial_number"] = decoding_char(mvcc_dev_info.SpecialInfo.stCXPInfo.chSerialNumber)

    elif mvcc_dev_info.nTLayerType == MV_GENTL_XOF_DEVICE:
        info["model_name"] = decoding_char(mvcc_dev_info.SpecialInfo.stXoFInfo.chModelName)
        info["serial_number"] = decoding_char(mvcc_dev_info.SpecialInfo.stXoFInfo.chSerialNumber)

    return info


def enumerate_devices() -> List[dict]:
    """枚举所有可用的海康相机设备

    Returns:
        设备信息字典列表
    """
    deviceList = MV_CC_DEVICE_INFO_LIST()
    tlayerType = (MV_GIGE_DEVICE | MV_USB_DEVICE | MV_GENTL_CAMERALINK_DEVICE
                  | MV_GENTL_CXP_DEVICE | MV_GENTL_XOF_DEVICE)

    ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
    if ret != 0:
        raise RuntimeError(f"枚举设备失败! ret[0x{ret:x}]")

    devices = []
    for i in range(deviceList.nDeviceNum):
        mvcc_dev_info = cast(deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
        info = get_device_info(mvcc_dev_info)
        info["index"] = i
        devices.append(info)

    return devices


# Bayer 格式到 OpenCV 颜色转换码的映射
# 海康相机的 Bayer 格式与 OpenCV 的定义对应关系
BAYER_TO_COLOR_CODE = {
    PixelType_Gvsp_BayerGR8: 0,   # BayerGR -> cv2.COLOR_BAYER_GR2BGR
    PixelType_Gvsp_BayerRG8: 1,   # BayerRG -> cv2.COLOR_BAYER_RG2BGR
    PixelType_Gvsp_BayerGB8: 2,   # BayerGB -> cv2.COLOR_BAYER_GB2BGR
    PixelType_Gvsp_BayerBG8: 3,   # BayerBG -> cv2.COLOR_BAYER_BG2BGR
    PixelType_Gvsp_BayerGR10: 0,
    PixelType_Gvsp_BayerRG10: 1,
    PixelType_Gvsp_BayerGB10: 2,
    PixelType_Gvsp_BayerBG10: 3,
    PixelType_Gvsp_BayerGR12: 0,
    PixelType_Gvsp_BayerRG12: 1,
    PixelType_Gvsp_BayerGB12: 2,
    PixelType_Gvsp_BayerBG12: 3,
    PixelType_Gvsp_BayerGR10_Packed: 0,
    PixelType_Gvsp_BayerRG10_Packed: 1,
    PixelType_Gvsp_BayerGB10_Packed: 2,
    PixelType_Gvsp_BayerBG10_Packed: 3,
    PixelType_Gvsp_BayerGR12_Packed: 0,
    PixelType_Gvsp_BayerRG12_Packed: 1,
    PixelType_Gvsp_BayerGB12_Packed: 2,
    PixelType_Gvsp_BayerBG12_Packed: 3,
}


def get_pixel_format_name(pixel_type: int) -> str:
    """获取像素格式名称"""
    format_names = {
        PixelType_Gvsp_Undefined: "Undefined",
        PixelType_Gvsp_Mono8: "Mono8",
        PixelType_Gvsp_Mono10: "Mono10",
        PixelType_Gvsp_Mono10_Packed: "Mono10_Packed",
        PixelType_Gvsp_Mono12: "Mono12",
        PixelType_Gvsp_Mono12_Packed: "Mono12_Packed",
        PixelType_Gvsp_Mono16: "Mono16",
        PixelType_Gvsp_BayerGR8: "BayerGR8",
        PixelType_Gvsp_BayerRG8: "BayerRG8",
        PixelType_Gvsp_BayerGB8: "BayerGB8",
        PixelType_Gvsp_BayerBG8: "BayerBG8",
        PixelType_Gvsp_BayerGR10: "BayerGR10",
        PixelType_Gvsp_BayerRG10: "BayerRG10",
        PixelType_Gvsp_BayerGB10: "BayerGB10",
        PixelType_Gvsp_BayerBG10: "BayerBG10",
        PixelType_Gvsp_BayerGR10_Packed: "BayerGR10_Packed",
        PixelType_Gvsp_BayerRG10_Packed: "BayerRG10_Packed",
        PixelType_Gvsp_BayerGB10_Packed: "BayerGB10_Packed",
        PixelType_Gvsp_BayerBG10_Packed: "BayerBG10_Packed",
        PixelType_Gvsp_BayerGR12: "BayerGR12",
        PixelType_Gvsp_BayerRG12: "BayerRG12",
        PixelType_Gvsp_BayerGB12: "BayerGB12",
        PixelType_Gvsp_BayerBG12: "BayerBG12",
        PixelType_Gvsp_BayerGR12_Packed: "BayerGR12_Packed",
        PixelType_Gvsp_BayerRG12_Packed: "BayerRG12_Packed",
        PixelType_Gvsp_BayerGB12_Packed: "BayerGB12_Packed",
        PixelType_Gvsp_BayerBG12_Packed: "BayerBG12_Packed",
        PixelType_Gvsp_RGB8_Packed: "RGB8_Packed",
        PixelType_Gvsp_BGR8_Packed: "BGR8_Packed",
        PixelType_Gvsp_RGBA8_Packed: "RGBA8_Packed",
        PixelType_Gvsp_BGRA8_Packed: "BGRA8_Packed",
        PixelType_Gvsp_YUV422_Packed: "YUV422_Packed",
        PixelType_Gvsp_YUV422_YUYV_Packed: "YUV422_YUYV_Packed",
    }
    return format_names.get(pixel_type, f"Unknown(0x{pixel_type:x})")


def is_bayer_format(pixel_type: int) -> bool:
    """判断是否为 Bayer 格式"""
    return pixel_type in BAYER_TO_COLOR_CODE


def is_mono_format(pixel_type: int) -> bool:
    """判断是否为单色格式"""
    mono_formats = [
        PixelType_Gvsp_Mono8,
        PixelType_Gvsp_Mono10,
        PixelType_Gvsp_Mono10_Packed,
        PixelType_Gvsp_Mono12,
        PixelType_Gvsp_Mono12_Packed,
        PixelType_Gvsp_Mono16,
    ]
    return pixel_type in mono_formats


def is_rgb_format(pixel_type: int) -> bool:
    """判断是否为 RGB 格式"""
    return pixel_type in (PixelType_Gvsp_RGB8_Packed, PixelType_Gvsp_BGR8_Packed,
                          PixelType_Gvsp_RGBA8_Packed, PixelType_Gvsp_BGRA8_Packed)
