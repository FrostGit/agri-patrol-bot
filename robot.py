#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WHEELTEC机器人底盘串口控制库
支持ROS教育机器人和大型ROS科研机器人底盘
作者: 基于WHEELTEC串口通信协议开发
版本: 1.0.0
"""

import serial
import struct
import time
import threading
from typing import Tuple, Optional, Callable
from dataclasses import dataclass


@dataclass
class RobotStatus:
    """机器人状态数据类"""
    # 电机使能状态
    motor_enabled: bool = False
    
    # 速度数据 (mm/s, mm/s, rad/s)
    velocity_x: float = 0.0  # X轴速度 mm/s
    velocity_y: float = 0.0  # Y轴速度 mm/s (仅全向轮支持)
    velocity_z: float = 0.0  # Z轴角速度 rad/s
    
    # 加速度数据 (m/s²)
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0
    
    # 角速度数据 (rad/s)
    gyro_x: float = 0.0
    gyro_y: float = 0.0
    gyro_z: float = 0.0
    
    # 电池电压 (V)
    battery_voltage: float = 0.0
    
    # 时间戳
    timestamp: float = 0.0


class WheeltecRobot:
    """WHEELTEC机器人底盘控制类"""
    
    # 协议常量
    FRAME_HEADER = 0x7B
    FRAME_TAIL = 0x7D
    UPLOAD_FRAME_LEN = 24  # 上行数据帧长度
    DOWNLOAD_FRAME_LEN = 11  # 下行数据帧长度
    
    # 传感器数据转换系数
    ACCEL_SCALE = 1672  # 加速度计原始数据转换系数
    GYRO_SCALE = 3753   # 陀螺仪原始数据转换系数
    
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.1, 
                 chassis_type: str = 'tracked'):
        """
        初始化WHEELTEC机器人
        
        Args:
            port: 串口设备名 (例如: '/dev/ttyUSB0' 或 'COM3')
            baudrate: 波特率，默认115200
            timeout: 串口读取超时时间（秒）
            chassis_type: 底盘类型，可选值:
                - 'tracked': 履带底盘（默认，仅支持vx和vz）
                - 'differential': 差速底盘（仅支持vx和vz）
                - 'ackermann': 阿克曼底盘（仅支持vx和vz）
                - 'mecanum': 麦克纳姆轮底盘（支持vx、vy、vz）
                - 'omni': 全向轮底盘（支持vx、vy、vz）
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.chassis_type = chassis_type.lower()
        
        # 验证底盘类型
        valid_types = ['tracked', 'differential', 'ackermann', 'mecanum', 'omni']
        if self.chassis_type not in valid_types:
            raise ValueError(f"不支持的底盘类型: {chassis_type}，有效类型: {valid_types}")
        
        # 判断是否支持Y轴运动
        self.support_y_axis = self.chassis_type in ['mecanum', 'omni']
        
        print(f"底盘类型: {self._get_chassis_name()}")
        if not self.support_y_axis:
            print("注意: 该底盘不支持Y轴（左右平移）运动")
        
        # 串口对象
        self.serial = None
        self.is_connected = False
        
        # 接收数据缓冲区
        self._rx_buffer = bytearray()
        
        # 机器人状态
        self.status = RobotStatus()
        
        # 数据接收线程
        self._rx_thread = None
        self._running = False
        
        # 状态更新回调函数
        self._status_callback: Optional[Callable[[RobotStatus], None]] = None
        
        # 线程锁
        self._lock = threading.Lock()
    
    def _get_chassis_name(self) -> str:
        """获取底盘类型的中文名称"""
        names = {
            'tracked': '履带底盘',
            'differential': '差速底盘',
            'ackermann': '阿克曼底盘',
            'mecanum': '麦克纳姆轮底盘',
            'omni': '全向轮底盘'
        }
        return names.get(self.chassis_type, '未知底盘')
    
    def connect(self) -> bool:
        """
        连接串口
        
        Returns:
            bool: 连接成功返回True，失败返回False
        """
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            self.is_connected = True
            print(f"✓ 成功连接到 {self.port}")
            return True
        except serial.SerialException as e:
            print(f"✗ 连接失败: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """断开串口连接"""
        self.stop_receive()
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.is_connected = False
            print("串口已断开")
    
    def start_receive(self, callback: Optional[Callable[[RobotStatus], None]] = None):
        """
        启动数据接收线程
        
        Args:
            callback: 状态更新回调函数，接收RobotStatus对象
        """
        if not self.is_connected:
            print("错误: 未连接串口")
            return
        
        if self._running:
            print("接收线程已在运行")
            return
        
        self._status_callback = callback
        self._running = True
        self._rx_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._rx_thread.start()
        print("数据接收线程已启动")
    
    def stop_receive(self):
        """停止数据接收线程"""
        self._running = False
        if self._rx_thread:
            self._rx_thread.join(timeout=1.0)
            print("数据接收线程已停止")
    
    def _receive_loop(self):
        """数据接收循环（运行在独立线程中）"""
        while self._running:
            try:
                if self.serial and self.serial.in_waiting > 0:
                    # 读取可用数据
                    data = self.serial.read(self.serial.in_waiting)
                    self._rx_buffer.extend(data)
                    
                    # 解析数据帧
                    self._parse_frames()
                else:
                    time.sleep(0.001)
            except Exception as e:
                print(f"接收数据错误: {e}")
                time.sleep(0.1)
    
    def _parse_frames(self):
        """解析接收缓冲区中的数据帧"""
        while len(self._rx_buffer) >= self.UPLOAD_FRAME_LEN:
            # 查找帧头
            try:
                header_index = self._rx_buffer.index(self.FRAME_HEADER)
            except ValueError:
                # 没有找到帧头，清空缓冲区
                self._rx_buffer.clear()
                break
            
            # 移除帧头之前的数据
            if header_index > 0:
                self._rx_buffer = self._rx_buffer[header_index:]
            
            # 检查是否有完整帧
            if len(self._rx_buffer) < self.UPLOAD_FRAME_LEN:
                break
            
            # 提取一帧数据
            frame = self._rx_buffer[:self.UPLOAD_FRAME_LEN]
            
            # 验证帧尾
            if frame[-1] != self.FRAME_TAIL:
                # 帧尾错误，移除帧头继续查找
                self._rx_buffer = self._rx_buffer[1:]
                continue
            
            # 验证校验和
            checksum = self._calculate_checksum(frame[:-2])
            if checksum != frame[-2]:
                print(f"校验和错误: 期望 {checksum:02X}, 收到 {frame[-2]:02X}")
                self._rx_buffer = self._rx_buffer[1:]
                continue
            
            # 解析数据帧
            self._parse_upload_frame(frame)
            
            # 移除已处理的帧
            self._rx_buffer = self._rx_buffer[self.UPLOAD_FRAME_LEN:]
    
    def _parse_upload_frame(self, frame: bytes):
        """
        解析上行数据帧
        
        Args:
            frame: 24字节的上行数据帧
        """
        try:
            with self._lock:
                # 电机使能状态
                self.status.motor_enabled = (frame[1] == 0x00)
                
                # X轴速度 (mm/s)
                self.status.velocity_x = struct.unpack('>h', frame[2:4])[0]
                
                # Y轴速度 (mm/s)
                self.status.velocity_y = struct.unpack('>h', frame[4:6])[0]
                
                # Z轴角速度 (rad/s) - 原始值放大了1000倍
                z_raw = struct.unpack('>h', frame[6:8])[0]
                self.status.velocity_z = z_raw / 1000.0
                
                # X轴加速度 (m/s²)
                accel_x_raw = struct.unpack('>h', frame[8:10])[0]
                self.status.accel_x = accel_x_raw / self.ACCEL_SCALE
                
                # Y轴加速度 (m/s²)
                accel_y_raw = struct.unpack('>h', frame[10:12])[0]
                self.status.accel_y = accel_y_raw / self.ACCEL_SCALE
                
                # Z轴加速度 (m/s²)
                accel_z_raw = struct.unpack('>h', frame[12:14])[0]
                self.status.accel_z = accel_z_raw / self.ACCEL_SCALE
                
                # X轴角速度 (rad/s)
                gyro_x_raw = struct.unpack('>h', frame[14:16])[0]
                self.status.gyro_x = gyro_x_raw / self.GYRO_SCALE
                
                # Y轴角速度 (rad/s)
                gyro_y_raw = struct.unpack('>h', frame[16:18])[0]
                self.status.gyro_y = gyro_y_raw / self.GYRO_SCALE
                
                # Z轴角速度 (rad/s)
                gyro_z_raw = struct.unpack('>h', frame[18:20])[0]
                self.status.gyro_z = gyro_z_raw / self.GYRO_SCALE
                
                # 电池电压 (V) - 原始值单位为mV
                voltage_raw = struct.unpack('>H', frame[20:22])[0]  # 使用无符号short
                self.status.battery_voltage = voltage_raw / 1000.0
                
                # 更新时间戳
                self.status.timestamp = time.time()
            
            # 调用回调函数
            if self._status_callback:
                self._status_callback(self.status)
                
        except Exception as e:
            print(f"解析数据帧错误: {e}")
    
    def set_velocity(self, vx: float = 0.0, vy: float = 0.0, vz: float = 0.0) -> bool:
        """
        设置机器人速度
        
        Args:
            vx: X轴速度 (mm/s)，正值向前，负值向后
            vy: Y轴速度 (mm/s)，正值向左，负值向右（仅全向轮/麦克纳姆轮支持）
            vz: Z轴角速度 (rad/s)，正值逆时针，负值顺时针
        
        Returns:
            bool: 发送成功返回True
        
        Note:
            履带底盘、差速底盘、阿克曼底盘不支持Y轴运动，vy参数将被忽略
        """
        if not self.is_connected:
            print("错误: 未连接串口")
            return False
        
        # 检查Y轴运动支持
        if not self.support_y_axis and abs(vy) > 0.1:
            print(f"警告: {self._get_chassis_name()}不支持Y轴运动，vy={vy}将被忽略")
            vy = 0.0
        
        try:
            # 构建下行数据帧
            frame = bytearray(self.DOWNLOAD_FRAME_LEN)
            
            # 帧头
            frame[0] = self.FRAME_HEADER
            
            # 预留位
            frame[1] = 0x00
            frame[2] = 0x00
            
            # X轴目标速度 (mm/s)
            vx_int = int(vx)
            frame[3:5] = struct.pack('>h', vx_int)
            
            # Y轴目标速度 (mm/s) - 履带底盘固定为0
            vy_int = int(vy) if self.support_y_axis else 0
            frame[5:7] = struct.pack('>h', vy_int)
            
            # Z轴目标速度 (rad/s * 1000)
            vz_int = int(vz * 1000)
            frame[7:9] = struct.pack('>h', vz_int)
            
            # 计算校验和
            checksum = self._calculate_checksum(frame[:-2])
            frame[9] = checksum
            
            # 帧尾
            frame[10] = self.FRAME_TAIL
            
            # 发送数据
            self.serial.write(frame)
            return True
            
        except Exception as e:
            print(f"发送速度命令错误: {e}")
            return False
    
    def stop(self) -> bool:
        """
        停止机器人（所有轴速度设为0）
        
        Returns:
            bool: 发送成功返回True
        """
        return self.set_velocity(0, 0, 0)
    
    def move_forward(self, speed: float = 100.0) -> bool:
        """
        向前移动
        
        Args:
            speed: 速度 (mm/s)，默认100
        """
        return self.set_velocity(vx=abs(speed))
    
    def move_backward(self, speed: float = 100.0) -> bool:
        """
        向后移动
        
        Args:
            speed: 速度 (mm/s)，默认100
        """
        return self.set_velocity(vx=-abs(speed))
    
    def move_left(self, speed: float = 100.0) -> bool:
        """
        向左平移（仅全向轮/麦克纳姆轮支持）
        
        Args:
            speed: 速度 (mm/s)，默认100
        
        Returns:
            bool: 发送成功返回True，不支持的底盘返回False
        """
        if not self.support_y_axis:
            print(f"错误: {self._get_chassis_name()}不支持左右平移")
            print("提示: 履带底盘请使用原地转向后前进")
            return False
        return self.set_velocity(vy=abs(speed))
    
    def move_right(self, speed: float = 100.0) -> bool:
        """
        向右平移（仅全向轮/麦克纳姆轮支持）
        
        Args:
            speed: 速度 (mm/s)，默认100
        
        Returns:
            bool: 发送成功返回True，不支持的底盘返回False
        """
        if not self.support_y_axis:
            print(f"错误: {self._get_chassis_name()}不支持左右平移")
            print("提示: 履带底盘请使用原地转向后前进")
            return False
        return self.set_velocity(vy=-abs(speed))
    
    def rotate_left(self, speed: float = 0.5) -> bool:
        """
        原地左转（逆时针）
        
        Args:
            speed: 角速度 (rad/s)，默认0.5
        """
        return self.set_velocity(vz=abs(speed))
    
    def rotate_right(self, speed: float = 0.5) -> bool:
        """
        原地右转（顺时针）
        
        Args:
            speed: 角速度 (rad/s)，默认0.5
        """
        return self.set_velocity(vz=-abs(speed))
    
    def get_status(self) -> RobotStatus:
        """
        获取当前机器人状态
        
        Returns:
            RobotStatus: 机器人状态数据
        """
        with self._lock:
            return RobotStatus(
                motor_enabled=self.status.motor_enabled,
                velocity_x=self.status.velocity_x,
                velocity_y=self.status.velocity_y,
                velocity_z=self.status.velocity_z,
                accel_x=self.status.accel_x,
                accel_y=self.status.accel_y,
                accel_z=self.status.accel_z,
                gyro_x=self.status.gyro_x,
                gyro_y=self.status.gyro_y,
                gyro_z=self.status.gyro_z,
                battery_voltage=self.status.battery_voltage,
                timestamp=self.status.timestamp
            )
    
    @staticmethod
    def _calculate_checksum(data: bytes) -> int:
        """
        计算BCC校验和（异或校验）
        
        Args:
            data: 要校验的数据
        
        Returns:
            int: 校验和
        """
        checksum = 0
        for byte in data:
            checksum ^= byte
        return checksum
    
    def __enter__(self):
        """支持with语句"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持with语句"""
        self.disconnect()
    
    def __del__(self):
        """析构函数"""
        self.disconnect()


# 便捷函数
def list_serial_ports():
    """
    列出所有可用的串口设备
    
    Returns:
        list: 串口设备列表
    """
    import serial.tools.list_ports
    ports = serial.tools.list_ports.comports()
    available_ports = []
    
    print("可用串口设备:")
    for port in ports:
        print(f"  - {port.device}: {port.description}")
        available_ports.append(port.device)
    
    return available_ports


if __name__ == "__main__":
    # 测试代码
    print("WHEELTEC机器人底盘控制库测试")
    print("=" * 50)
    
    # 列出可用串口
    ports = list_serial_ports()
    
    if not ports:
        print("\n未找到可用串口设备")
    else:
        print(f"\n请手动修改代码中的串口号，然后运行测试")