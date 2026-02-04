#!/usr/bin/env python3
"""
树莓派相机视频流服务器
使用 Picamera2 库捕获视频并通过 Flask 提供 MJPEG 流
"""

from flask import Flask, Response, render_template_string
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
import io
import threading
import time

app = Flask(__name__)

# 全局变量
output = None
picam2 = None
streaming_output = None


class StreamingOutput(io.BufferedIOBase):
    """用于捕获JPEG帧的输出类"""
    
    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


def initialize_camera():
    """初始化相机"""
    global picam2, streaming_output
    
    picam2 = Picamera2()
    
    # 配置相机 - 使用较低分辨率以获得更好的流畅度
    config = picam2.create_video_configuration(
        main={"size": (640, 480), "format": "RGB888"}
    )
    picam2.configure(config)
    
    # 创建流输出
    streaming_output = StreamingOutput()
    
    # 启动相机
    picam2.start()
    print("相机初始化成功")


def generate_frames():
    """生成MJPEG流的帧"""
    global picam2
    
    try:
        while True:
            # 捕获JPEG格式的图像
            buffer = io.BytesIO()
            picam2.capture_file(buffer, format='jpeg')
            frame = buffer.getvalue()
            
            # 生成MJPEG流格式
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            
            # 控制帧率 (约30fps)
            time.sleep(0.033)
            
    except Exception as e:
        print(f"生成帧时出错: {e}")


# HTML模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>树莓派相机视频流</title>
    <style>
        body {
            margin: 0;
            padding: 20px;
            font-family: Arial, sans-serif;
            background-color: #f0f0f0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }
        
        h1 {
            color: #333;
            margin-bottom: 20px;
        }
        
        .container {
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            max-width: 800px;
            width: 100%;
        }
        
        .video-container {
            position: relative;
            width: 100%;
            padding-bottom: 75%; /* 4:3 宽高比 */
            background-color: #000;
            border-radius: 5px;
            overflow: hidden;
        }
        
        .video-container img {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: contain;
        }
        
        .info {
            margin-top: 20px;
            padding: 15px;
            background-color: #e8f4f8;
            border-radius: 5px;
            border-left: 4px solid #2196F3;
        }
        
        .info p {
            margin: 5px 0;
            color: #555;
        }
        
        .status {
            display: inline-block;
            width: 10px;
            height: 10px;
            background-color: #4CAF50;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% {
                opacity: 1;
            }
            50% {
                opacity: 0.5;
            }
        }
        
        @media (max-width: 600px) {
            body {
                padding: 10px;
            }
            
            h1 {
                font-size: 24px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎥 树莓派相机实时视频流</h1>
        
        <div class="video-container">
            <img src="{{ url_for('video_feed') }}" alt="视频流加载中...">
        </div>
        
        <div class="info">
            <p><span class="status"></span><strong>状态:</strong> 正在直播</p>
            <p><strong>分辨率:</strong> 640 x 480</p>
            <p><strong>设备:</strong> 树莓派 4B + Picamera2</p>
            <p><strong>提示:</strong> 视频流使用 MJPEG 格式传输</p>
        </div>
    </div>
</body>
</html>
"""


@app.route('/')
def index():
    """主页面"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/video_feed')
def video_feed():
    """视频流路由"""
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/status')
def status():
    """状态检查接口"""
    return {
        'status': 'running',
        'camera': 'active',
        'resolution': '640x480'
    }


def cleanup():
    """清理资源"""
    global picam2
    if picam2:
        picam2.stop()
        picam2.close()
        print("相机资源已释放")


if __name__ == '__main__':
    try:
        print("正在初始化相机...")
        initialize_camera()
        
        print("\n" + "="*50)
        print("视频流服务器已启动!")
        print("="*50)
        print("请在浏览器中访问:")
        print("  本地: http://localhost:5000")
        print("  局域网: http://<树莓派IP>:5000")
        print("="*50)
        print("\n按 Ctrl+C 停止服务器\n")
        
        # 启动Flask服务器
        app.run(
            host='0.0.0.0',  # 允许外部访问
            port=5000,
            debug=False,
            threaded=True
        )
        
    except KeyboardInterrupt:
        print("\n正在关闭服务器...")
    except Exception as e:
        print(f"错误: {e}")
    finally:
        cleanup()