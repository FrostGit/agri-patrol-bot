from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import time
import random

app = Flask(__name__, static_folder='static')
CORS(app)  # 允许跨域请求

# 模拟硬件设备数据
device_data = {
    "battery": 98,
    "sensor_time": "09:00",
    "power_level": 600,
    "signal_strength": 97,
    "devices": [
        {"name": "主控制器", "status": "online", "value": 70},
        {"name": "传感器1", "status": "online", "value": 90},
        {"name": "传感器2", "status": "online", "value": 90},
        {"name": "执行机构", "status": "online", "value": 50}
    ],
    "chart_data": [60, 45, 75, 30, 55, 40],
    "risk_level": 5,
    "alert_count": 0,
    "trend_stat": 200
}

# 模拟机器人位置数据
robot_data = {
    "x": 50,
    "y": 50,
    "status": "running",
    "battery": 95,
    "speed": 2.5
}

# 模拟病虫害数据
pest_data = [
    {"name": "白粉虱", "icon": "🐛", "percentage": 10},
    {"name": "玉米螟", "icon": "🦗", "percentage": 10},
    {"name": "蚜虫", "icon": "🐜", "percentage": 10},
    {"name": "地老虎", "icon": "🦟", "percentage": 10},
    {"name": "稻飞虱", "icon": "🐝", "percentage": 10},
    {"name": "甜菜夜蛾", "icon": "🦂", "percentage": 10}
]

# 模拟核心功能统计数据
core_stats_data = {
    "statistics": 15,
    "effect": 2.7,
    "efficiency": 3.15,
    "energy_consumption": 2.3,
    "speed": 2.00,
    "recognition_rate": 5.13,
    "computing_power": 3.20
}

# 模拟防治方案数据
solution_data = {
    "leaf_position": "第1片",
    "pest_type": "玉米螟",
    "harm_level": 1.0,
    "recommended_agent": "1500倍液",
    "pesticide_residue": "无",
    "control_cycle": "1-3天"
}

# 模拟底部解决方案数据
bottom_solutions = [
    {"icon": "💧", "title": "阳台养植", "value": "56/L"},
    {"icon": "⚡", "title": "联合养", "value": "200"},
    {"icon": "🌱", "title": "藤蔓系列", "value": "50:1"},
    {"icon": "🎯", "title": "报告营养", "value": "999L"}
]

@app.route('/')
def index():
    """
    首页路由，返回HTML页面
    """
    return send_from_directory('static', 'index.html')

@app.route('/api/device/status', methods=['GET'])
def get_device_status():
    """
    获取设备状态数据API
    接口说明：返回当前设备的各项状态参数
    请求方式：GET
    返回数据：
    - battery: 电池电量（%）
    - sensor_time: 传感器时间
    - power_level: 功率水平
    - signal_strength: 信号强度（%）
    - devices: 设备列表
    - chart_data: 图表数据
    - risk_level: 风险等级
    - alert_count: 预警次数
    - trend_stat: 趋势统计
    """
    # 模拟实时数据更新
    device_data['battery'] = random.randint(90, 100)
    device_data['signal_strength'] = random.randint(90, 100)
    device_data['chart_data'] = [random.randint(20, 80) for _ in range(6)]
    device_data['risk_level'] = random.randint(0, 10)
    
    return jsonify(device_data)

@app.route('/api/robot/status', methods=['GET'])
def get_robot_status():
    """
    获取机器人状态API
    接口说明：返回机器人的当前状态和位置信息
    请求方式：GET
    返回数据：
    - x: X坐标
    - y: Y坐标
    - status: 状态（running/stopped/idle）
    - battery: 电池电量（%）
    - speed: 速度
    """
    # 模拟机器人移动
    robot_data['x'] = random.randint(10, 90)
    robot_data['y'] = random.randint(10, 90)
    robot_data['battery'] = random.randint(90, 100)
    robot_data['speed'] = round(random.uniform(1.0, 3.0), 1)
    
    return jsonify(robot_data)

@app.route('/api/robot/control', methods=['POST'])
def control_robot():
    """
    控制机器人API
    接口说明：发送指令控制机器人的移动和动作
    请求方式：POST
    请求数据：
    - command: 指令类型（move/stop/scan）
    - x: 目标X坐标（仅move指令需要）
    - y: 目标Y坐标（仅move指令需要）
    返回数据：
    - success: 是否成功
    - message: 执行结果消息
    - data: 机器人当前状态
    """
    try:
        data = request.get_json()
        command = data.get('command')
        
        if command == 'move':
            x = data.get('x')
            y = data.get('y')
            if x is not None and y is not None:
                robot_data['x'] = x
                robot_data['y'] = y
                robot_data['status'] = 'running'
                return jsonify({
                    'success': True,
                    'message': f'机器人正在移动到 ({x}, {y})',
                    'data': robot_data
                })
            else:
                return jsonify({'success': False, 'message': '缺少目标坐标'}), 400
        
        elif command == 'stop':
            robot_data['status'] = 'stopped'
            return jsonify({
                'success': True,
                'message': '机器人已停止',
                'data': robot_data
            })
        
        elif command == 'scan':
            robot_data['status'] = 'scanning'
            return jsonify({
                'success': True,
                'message': '机器人开始扫描',
                'data': robot_data
            })
        
        else:
            return jsonify({'success': False, 'message': '未知指令'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/stats/core', methods=['GET'])
def get_core_stats():
    """
    获取核心功能统计数据API
    接口说明：返回系统核心功能的统计信息
    请求方式：GET
    返回数据：
    - statistics: 统计值
    - effect: 效果倍数
    - efficiency: 效率值
    - energy_consumption: 能耗值
    - speed: 速度值
    - recognition_rate: 识别率
    - computing_power: 计算力
    """
    # 模拟数据波动
    for key in core_stats_data:
        if key == 'statistics':
            core_stats_data[key] = random.randint(10, 20)
        elif key == 'recognition_rate':
            core_stats_data[key] = round(random.uniform(4.0, 6.0), 2)
        else:
            core_stats_data[key] = round(random.uniform(1.0, 4.0), 2)
    
    return jsonify(core_stats_data)

@app.route('/api/pests', methods=['GET'])
def get_pest_data():
    """
    获取病虫害识别统计数据API
    接口说明：返回各种病虫害的识别统计信息
    请求方式：GET
    返回数据：
    - name: 病虫害名称
    - icon: 图标
    - percentage: 百分比
    """
    # 模拟数据更新
    for pest in pest_data:
        pest['percentage'] = random.randint(5, 15)
    
    return jsonify(pest_data)

@app.route('/api/solution', methods=['GET'])
def get_solution():
    """
    获取防治方案数据API
    接口说明：返回当前的防治方案信息
    请求方式：GET
    返回数据：
    - leaf_position: 叶片定位
    - pest_type: 病虫害类型
    - harm_level: 危害程度
    - recommended_agent: 推荐药剂
    - pesticide_residue: 农残标准
    - control_cycle: 防治周期
    """
    return jsonify(solution_data)

@app.route('/api/solution/bottom', methods=['GET'])
def get_bottom_solutions():
    """
    获取底部解决方案数据API
    接口说明：返回底部展示的解决方案数据
    请求方式：GET
    返回数据：
    - icon: 图标
    - title: 标题
    - value: 值
    """
    return jsonify(bottom_solutions)

@app.route('/api/data/update', methods=['POST'])
def update_data():
    """
    更新设备数据API
    接口说明：接收硬件设备发送的实时数据并更新
    请求方式：POST
    请求数据：
    - device_id: 设备ID
    - data_type: 数据类型
    - value: 数据值
    返回数据：
    - success: 是否成功
    - message: 处理结果消息
    """
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        data_type = data.get('data_type')
        value = data.get('value')
        
        # 这里可以添加实际的数据处理逻辑
        # 例如将数据存储到数据库或转发到其他系统
        
        return jsonify({
            'success': True,
            'message': f'数据已更新：设备 {device_id}，类型 {data_type}，值 {value}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    # 运行Flask应用，监听所有IP地址，端口5000
    app.run(host='0.0.0.0', port=5000, debug=True)