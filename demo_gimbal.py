# *-* coding: utf-8 *-*

"""
树莓派 云台控制与相机实时预览程序
功能：
    1. 控制云台持续摇头（巡逻模式）
    2. 打开相机实时显示画面（自动检测图形环境，支持 Qt/DRM 预览）
    3. 支持优雅退出（Ctrl+C）
硬件依赖：
    - Raspberry Pi 4
    - PCA9685 驱动板 (地址 0x41)
    - 相机模块(请注意：硬件相机有可能出现虚接情况，如报错，请检查相机侧的连接线是否牢固)
"""
import cv2
import sys
import signal
import logging
import threading
import time
import board
from adafruit_pca9685 import PCA9685
from picamera2 import Picamera2

# --- 配置常量 ---
# PCA9685 配置
PCA_ADDRESS = 0x41
PWM_FREQ = 60  # 舵机工作频率 (Hz)

# 通道定义
CH_SERVO_PAN = 1  # 云台水平舵机通道

# PWM 占空比值 (16-bit resolution, 0x0000 - 0xFFFF，对应 0% - 100%)
# 以下值根据实际舵机调试确定，请务必测试后微调
SERVO_MIN = 0x1000  # 左极限 (4096 / 65535 ≈ 6.25% 占空比)
SERVO_MID = 0x1300  # 中位 (4864 / 65535 ≈ 7.42% 占空比)
SERVO_MAX = 0x2000  # 右极限 (8192 / 65535 ≈ 12.5% 占空比)
SERVO_STEP = 0x5F   # 步进增量 (95)，决定旋转速度

# 全局运行标志
RUNNING = True

# --- 日志配置（修正编码）---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'  # 解决中文乱码
)
logger = logging.getLogger("GimbalCam")

# --- 信号处理 (用于优雅退出) ---
def signal_handler(sig, frame):
    global RUNNING
    logger.info("收到停止信号，正在关闭系统...")
    RUNNING = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# --- 云台控制类 ---
class GimbalController:
    def __init__(self):
        self.pca = None
        self.is_initialized = False

    def init(self):
        """初始化PCA9685"""
        try:
            i2c = board.I2C()
            self.pca = PCA9685(i2c, address=PCA_ADDRESS)
            self.pca.frequency = PWM_FREQ
            self.is_initialized = True
            logger.info("PCA9685 初始化成功")
        except Exception as e:
            logger.error(f"PCA9685 初始化失败：{e}")
            self.is_initialized = False

    def set_servo(self, duty_cycle: int):
        """设置舵机PWM占空比，自动限制安全范围"""
        if not self.is_initialized:
            return
        # 限制占空比在0x0000-0xFFFF之间，防止硬件损坏
        safe_duty = max(0x0000, min(0xFFFF, duty_cycle))
        self.pca.channels[CH_SERVO_PAN].duty_cycle = safe_duty

    def patrol_loop(self):
        """云台巡逻逻辑 (持续左右摇头)"""
        if not self.is_initialized:
            return
            
        logger.info("开始云台巡逻...")
        
        # 舵机归中位
        self.set_servo(SERVO_MID)
        time.sleep(0.5)

        while RUNNING:
            # 向右转 (SERVO_MID -> SERVO_MAX)
            for i in range(SERVO_MID, SERVO_MAX, SERVO_STEP):
                if not RUNNING:
                    break
                self.set_servo(i)
                time.sleep(0.03)
            
            # 向左转 (SERVO_MAX -> SERVO_MIN)
            for i in range(SERVO_MAX, SERVO_MIN, -SERVO_STEP):
                if not RUNNING:
                    break
                self.set_servo(i)
                time.sleep(0.03)
            
            # 回到中位 (SERVO_MIN -> SERVO_MID)
            for i in range(SERVO_MIN, SERVO_MID, SERVO_STEP):
                if not RUNNING:
                    break
                self.set_servo(i)
                time.sleep(0.03)
                
        # 退出巡逻，舵机归位
        self.set_servo(SERVO_MID)
        logger.info("云台巡逻已停止，舵机归位")

    def cleanup(self):
        """释放资源"""
        if self.pca:
            try:
                self.set_servo(SERVO_MID)
                logger.info("云台控制器资源已释放")
            except Exception as e:
                logger.error(f"清理云台资源时出错：{e}")

# --- 相机功能函数 ---
def camera_loop():
    """相机预览循环（使用 OpenCV 显示，兼容各种格式）"""
    global RUNNING  # 声明全局变量，放在最前面
    picam2 = None
    try:
        logger.info("正在初始化相机...")
        picam2 = Picamera2()
        
        # 配置预览参数（保留原有配置，OpenCV 可处理多种格式）
        preview_config = picam2.create_preview_configuration(main={"size": (640, 480)})
        picam2.configure(preview_config)
        
        picam2.start()
        logger.info("相机已启动，正在打开 OpenCV 预览窗口...")
        
        cv2.namedWindow("Camera Preview", cv2.WINDOW_NORMAL)
        
        while RUNNING:
            frame = picam2.capture_array()
            
            # 如果图像是 3 通道，假设为 RGB，转换为 BGR 供 OpenCV 显示
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            cv2.imshow("Camera Preview", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # q 或 ESC 退出
                logger.info("用户通过预览窗口请求退出")
                RUNNING = False
                break
                
    except Exception as e:
        logger.error(f"相机运行错误：{e}")
    finally:
        if picam2:
            try:
                picam2.stop()
                picam2.close()
                logger.info("相机资源已释放")
            except Exception as e:
                logger.error(f"清理相机资源时出错：{e}，请检查相机侧连接线是否牢固")
        cv2.destroyAllWindows()
        logger.info("OpenCV 窗口已关闭")

# --- 主程序入口 ---
if __name__ == "__main__":
    logger.info("云台与相机测试程序启动")
    
    # 初始化云台
    gimbal = GimbalController()
    gimbal.init()
    
    if not gimbal.is_initialized:
        logger.error("云台初始化失败，程序退出。")
        sys.exit(1)

    # 创建线程
    gimbal_thread = threading.Thread(target=gimbal.patrol_loop, name="GimbalThread")
    camera_thread = threading.Thread(target=camera_loop, name="CameraThread")

    try:
        gimbal_thread.start()
        camera_thread.start()
        
        # 主线程等待子线程结束
        gimbal_thread.join()
        camera_thread.join()
        
    except KeyboardInterrupt:
        # 已经通过信号处理捕获，这里仅作后备
        pass
    finally:
        RUNNING = False
        # 给线程一点时间响应退出标志
        time.sleep(0.5) 
        gimbal.cleanup()
        logger.info("程序完全退出")