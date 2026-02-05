#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
农业巡检智能服务应用 - 树莓派4B+ 后端
适用于树莓派4B+ 4G，使用picamera2捕获USB相机
"""

from flask import Flask, Response, jsonify, send_from_directory
import cv2
import numpy as np
from datetime import datetime
import threading
import time
import json

# 尝试导入picamera2，如果失败则使用cv2作为备用
try:
    from picamera2 import Picamera2
    USE_PICAMERA2 = True
except ImportError:
    print("警告: picamera2未安装，将使用OpenCV作为备用方案")
    USE_PICAMERA2 = False

app = Flask(__name__, static_folder='static')

# ==================== 全局变量 ====================
current_frame = None
frame_lock = threading.Lock()
robot_position = {"x": 50, "y": 50}  # 机器人位置（百分比）
camera = None

# ==================== 摄像头管理 ====================
class CameraManager:
    """摄像头管理类"""
    
    def __init__(self):
        self.camera = None
        self.running = False
        self.frame = None
        self.lock = threading.Lock()
        
    def start(self):
        """启动摄像头"""
        global USE_PICAMERA2
        
        if USE_PICAMERA2:
            try:
                # 使用picamera2捕获USB相机
                self.camera = Picamera2()
                
                # 配置相机 - 针对USB相机优化
                config = self.camera.create_video_configuration(
                    main={"size": (640, 480), "format": "RGB888"}
                )
                self.camera.configure(config)
                self.camera.start()
                
                print("✓ Picamera2 USB相机启动成功")
                self.running = True
                
                # 启动帧捕获线程
                threading.Thread(target=self._capture_picamera2, daemon=True).start()
                return True
                
            except Exception as e:
                print(f"✗ Picamera2启动失败: {e}")
                print("尝试使用OpenCV备用方案...")
                USE_PICAMERA2 = False
        
        # OpenCV备用方案
        if not USE_PICAMERA2:
            try:
                # 使用OpenCV打开USB相机
                self.camera = cv2.VideoCapture(0)  # /dev/video0
                
                # 设置分辨率和帧率
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.camera.set(cv2.CAP_PROP_FPS, 15)
                
                if not self.camera.isOpened():
                    raise Exception("无法打开摄像头")
                
                print("✓ OpenCV USB相机启动成功")
                self.running = True
                
                # 启动帧捕获线程
                threading.Thread(target=self._capture_opencv, daemon=True).start()
                return True
                
            except Exception as e:
                print(f"✗ OpenCV启动失败: {e}")
                return False
    
    def _capture_picamera2(self):
        """Picamera2帧捕获线程"""
        while self.running:
            try:
                # 捕获帧
                frame = self.camera.capture_array()
                
                # 转换为BGR格式（OpenCV格式）
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # 更新帧
                with self.lock:
                    self.frame = frame_bgr
                
                time.sleep(1/15)  # 15 FPS
                
            except Exception as e:
                print(f"帧捕获错误: {e}")
                time.sleep(0.1)
    
    def _capture_opencv(self):
        """OpenCV帧捕获线程"""
        while self.running:
            try:
                ret, frame = self.camera.read()
                if ret:
                    with self.lock:
                        self.frame = frame
                else:
                    print("读取帧失败")
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"帧捕获错误: {e}")
                time.sleep(0.1)
    
    def get_frame(self):
        """获取当前帧"""
        with self.lock:
            if self.frame is not None:
                return self.frame.copy()
            return None
    
    def stop(self):
        """停止摄像头"""
        self.running = False
        time.sleep(0.2)
        
        if self.camera is not None:
            if USE_PICAMERA2:
                try:
                    self.camera.stop()
                except:
                    pass
            else:
                self.camera.release()
        
        print("摄像头已停止")

# 初始化摄像头管理器
camera_manager = CameraManager()

# ==================== 视频流生成 ====================
def generate_frames():
    """生成视频流帧"""
    while True:
        frame = camera_manager.get_frame()
        
        if frame is None:
            # 如果没有帧，生成黑色占位图
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "Camera Not Available", (150, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # 添加时间戳叠加层（可选）
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # 添加机器人位置指示（可选）
        pos_text = f"Robot: ({robot_position['x']}, {robot_position['y']})"
        cv2.putText(frame, pos_text, (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # 编码为JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        
        if not ret:
            continue
        
        frame_bytes = buffer.tobytes()
        
        # 生成multipart响应
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(1/15)  # 15 FPS

# ==================== API路由 ====================

@app.route('/')
def index():
    """主页"""
    return send_from_directory('static', 'index.html')

@app.route('/video_feed')
def video_feed():
    """视频流端点"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/device/status')
def get_device_status():
    """获取设备状态"""
    try:
        # 读取系统信息（树莓派特定）
        cpu_usage = get_cpu_usage()
        memory_usage = get_memory_usage()
        cpu_temp = get_cpu_temperature()
        
        return jsonify({
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage,
            "power_level": 100,  # 电量，如果有UPS可以读取实际值
            "signal_strength": 97,  # WiFi信号强度
            "chart_data": [60, 45, 75, 30, 55, 40],  # 病虫害统计图表数据
            "risk_level": 5,
            "alert_count": 0,
            "trend_stat": 200,
            "cpu_temperature": cpu_temp
        })
    except Exception as e:
        print(f"获取设备状态错误: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/robot/status')
def get_robot_status():
    """获取机器人状态"""
    return jsonify({
        "x": robot_position["x"],
        "y": robot_position["y"],
        "battery": 100,
        "status": "online"
    })

@app.route('/api/robot/control', methods=['POST'])
def control_robot():
    """控制机器人移动"""
    from flask import request
    
    try:
        data = request.get_json()
        command = data.get('command')
        
        if command == 'move':
            x = data.get('x', 50)
            y = data.get('y', 50)
            
            # 更新机器人位置
            robot_position['x'] = max(0, min(100, x))
            robot_position['y'] = max(0, min(100, y))
            
            return jsonify({
                "success": True,
                "message": f"机器人移动到 ({x}, {y})",
                "position": robot_position
            })
        else:
            return jsonify({
                "success": False,
                "message": "未知命令"
            }), 400
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/api/stats/core')
def get_core_stats():
    """获取核心功能统计"""
    return jsonify({
        "statistics": 15,
        "effect": 2.7,
        "efficiency": 3.15,
        "energy_consumption": 2.3,
        "speed": 2.00,
        "recognition_rate": 5.13,
        "computing_power": 3.20
    })

@app.route('/api/pests')
def get_pests():
    """获取病虫害数据"""
    return jsonify([
        {"icon": "🐛", "name": "蚜虫", "percentage": 23},
        {"icon": "🦗", "name": "蝗虫", "percentage": 15},
        {"icon": "🍄", "name": "真菌", "percentage": 12}
    ])

@app.route('/api/solution')
def get_solution():
    """获取防治方案"""
    return jsonify({
        "leaf_position": "A区-3号",
        "pest_type": "蚜虫",
        "harm_level": "中度",
        "recommended_agent": "吡虫啉",
        "pesticide_residue": "≤0.5mg/kg",
        "control_cycle": "7-10天"
    })

@app.route('/api/solution/bottom')
def get_bottom_solutions():
    """获取底部解决方案数据 - 方案D：混合监控型"""
    return jsonify([
        {"icon": "💧", "title": "水分消耗", "value": "56L"},
        {"icon": "⚡", "title": "电力消耗", "value": "200kWh"},
        {"icon": "🌱", "title": "作物健康度", "value": "92%"},
        {"icon": "🎯", "title": "巡检进度", "value": "68%"}
    ])

# ==================== 系统信息获取函数 ====================

def get_cpu_usage():
    """获取CPU使用率"""
    try:
        # 使用psutil库（需要安装: pip3 install psutil）
        import psutil
        return round(psutil.cpu_percent(interval=1))
    except ImportError:
        # 备用方案：读取/proc/stat
        try:
            with open('/proc/stat', 'r') as f:
                line = f.readline()
                cpu_times = [float(x) for x in line.split()[1:]]
                idle_time = cpu_times[3]
                total_time = sum(cpu_times)
                usage = 100 * (1 - idle_time / total_time)
                return round(usage)
        except:
            return 45  # 默认值

def get_memory_usage():
    """获取内存使用率"""
    try:
        # 使用psutil库
        import psutil
        return round(psutil.virtual_memory().percent)
    except ImportError:
        # 备用方案：读取/proc/meminfo
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
                mem_total = int(lines[0].split()[1])
                mem_available = int(lines[2].split()[1])
                usage = 100 * (1 - mem_available / mem_total)
                return round(usage)
        except:
            return 62  # 默认值

def get_cpu_temperature():
    """获取CPU温度（树莓派专用）"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read().strip()) / 1000.0
            return round(temp, 1)
    except:
        return 0.0

# ==================== 主程序 ====================

if __name__ == '__main__':
    print("=" * 50)
    print("农业巡检智能服务应用 - 树莓派4B+ 后端")
    print("=" * 50)
    
    # 启动摄像头
    print("\n正在启动摄像头...")
    if camera_manager.start():
        print("✓ 摄像头启动成功\n")
    else:
        print("✗ 摄像头启动失败，视频流将不可用\n")
    
    # 启动Flask服务器
    print("启动Flask服务器...")
    print("访问地址: http://<树莓派IP>:5000")
    print("按Ctrl+C停止服务器\n")
    
    try:
        # 在树莓派上运行，监听所有接口
        app.run(
            host='0.0.0.0',  # 允许外部访问
            port=5000,
            debug=False,  # 生产环境关闭debug
            threaded=True  # 启用多线程
        )
    except KeyboardInterrupt:
        print("\n正在关闭服务器...")
    finally:
        camera_manager.stop()
        print("服务器已停止")