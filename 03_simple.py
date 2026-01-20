# -- coding: utf-8 --
"""海康相机简洁接口测试"""

import sys
import os

# 确保 src 目录在路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from hikcamera import HikCamera, HikCameraConfig, CameraParams, device_list

def test_list_devices():
    """测试设备枚举"""
    print("=" * 50)
    print("测试 1: 枚举设备")
    print("=" * 50)
    devices = device_list()
    print(f"找到 {len(devices)} 个设备:")
    for dev in devices:
        print(f"  - 索引: {dev['index']}")
        print(f"    类型: {dev['type']}")
        print(f"    型号: {dev['model_name']}")
        print(f"    IP: {dev['ip_address']}")
        print()
    return devices


def test_basic_capture():
    """测试基本采集"""
    print("=" * 50)
    print("测试 2: 基本图像采集")
    print("=" * 50)

    try:
        # 使用上下文管理器
        with HikCamera() as camera:
            print(f"设备信息: {camera.device_info}")
            print(f"触发模式: {camera.trigger_mode}")

            # 开始采集
            camera.start()
            print("相机已启动")

            # 获取图像
            image = camera.get_image()
            print(f"图像形状: {image.shape}")
            print(f"图像类型: {image.dtype}")

            # 保存图像
            import cv2
            cv2.imwrite("test_capture.jpg", image)
            print("图像已保存到 test_capture.jpg")

            # 停止采集
            camera.stop()
            print("相机已停止")

        print("测试通过!")
        return True

    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_trigger_mode():
    """测试触发模式"""
    print("\n" + "=" * 50)
    print("测试 3: 触发模式")
    print("=" * 50)

    try:
        config = HikCameraConfig(trigger_mode="trigger")
        with HikCamera(config=config) as camera:
            print(f"触发模式: {camera.trigger_mode}")

            camera.start()
            print("相机已启动（触发模式）")

            # 触发并获取图像
            image = camera.trigger_and_get_image()
            print(f"图像形状: {image.shape}")

            camera.stop()
            print("相机已停止")

        print("触发模式测试通过!")
        return True

    except Exception as e:
        print(f"触发模式测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_camera_properties():
    """测试相机属性设置"""
    print("\n" + "=" * 50)
    print("测试 4: 相机属性")
    print("=" * 50)

    try:
        with HikCamera() as camera:
            camera.start()

            # 读取属性
            print(f"初始宽度: {camera.width}")
            print(f"初始高度: {camera.height}")
            print(f"初始曝光: {camera.exposure}")
            print(f"初始增益: {camera.gain}")
            print(f"初始帧率: {camera.fps}")

            # 设置曝光
            camera.exposure = 5000
            print(f"设置曝光为 5000 后: {camera.exposure}")

            camera.stop()

        print("属性测试通过!")
        return True

    except Exception as e:
        print(f"属性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_continuous_capture():
    """测试连续采集多帧"""
    print("\n" + "=" * 50)
    print("测试 5: 连续采集多帧")
    print("=" * 50)

    try:
        with HikCamera() as camera:
            camera.start()
            print("开始连续采集 5 帧...")

            import cv2
            for i in range(5):
                image = camera.get_image()
                print(f"  帧 {i+1}: 形状 {image.shape}")
                cv2.imwrite(f"frame_{i+1}.jpg", image)

            camera.stop()
            print("连续采集测试通过!")
            return True

    except Exception as e:
        print(f"连续采集测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_params():
    """测试参数查询和设置"""
    print("\n" + "=" * 50)
    print("测试 6: 参数查询与设置")
    print("=" * 50)

    try:
        with HikCamera() as camera:
            camera.start()

            # 查询当前参数
            params = camera.get_params()
            print("当前相机参数:")
            print(f"  {params}")
            print()

            # 设置参数（使用当前值附近，确保在有效范围内）
            current_gain = params.gain
            new_gain = max(0, current_gain - 5) if current_gain > 5 else current_gain + 5
            new_fps = max(1, params.fps - 1)

            print("设置参数...")
            camera.set_params(
                exposure=8000,
                gain=new_gain,
                fps=new_fps,
            )
            print("参数设置完成")

            # 重新查询确认
            new_params = camera.get_params()
            print("设置后的相机参数:")
            print(f"  {new_params}")
            print()

            # 验证参数（允许一定误差）
            assert abs(new_params.exposure - 8000) < 100, f"曝光设置失败: {new_params.exposure}"
            assert abs(new_params.fps - new_fps) < 1.0, f"帧率设置失败: {new_params.fps}"

            camera.stop()

        print("参数查询与设置测试通过!")
        return True

    except Exception as e:
        print(f"参数查询与设置测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("海康相机简洁接口测试")
    print("=" * 50)

    # 测试设备枚举
    test_list_devices()

    # 测试基本采集
    test_basic_capture()

    # 测试触发模式
    test_trigger_mode()

    # 测试相机属性
    test_camera_properties()

    # 测试连续采集
    test_continuous_capture()

    # 测试参数查询与设置
    test_params()

    print("\n" + "=" * 50)
    print("所有测试完成!")
    print("=" * 50)
