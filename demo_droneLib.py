#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WHEELTEC履带底盘控制库 - 使用示例
履带底盘特点：差速驱动，仅支持前后移动和原地转向
"""

from robot import WheeltecRobot, RobotStatus, list_serial_ports
import time
import math


def status_callback(status: RobotStatus):
    """状态更新回调函数 - 履带底盘版"""
    print(f"\r[履带底盘] "
          f"电机: {'ON ' if status.motor_enabled else 'OFF'} | "
          f"速度: X={status.velocity_x:6.1f}mm/s Z={status.velocity_z:5.3f}rad/s | "
          f"电压: {status.battery_voltage:.2f}V", end='')


def example_1_basic_tracked_control():
    """示例1: 履带底盘基本控制 - 前进、后退、转向"""
    print("=" * 60)
    print("示例1: 履带底盘基本控制")
    print("=" * 60)
    
    PORT = '/dev/ttyACM0'  # 修改为您的串口号
    
    # 创建履带底盘机器人对象
    robot = WheeltecRobot(port=PORT, chassis_type='tracked')
    
    try:
        if not robot.connect():
            return
        
        robot.start_receive(callback=status_callback)
        time.sleep(1)
        
        print("\n\n1. 前进 200mm/s，持续3秒")
        robot.move_forward(speed=200)
        time.sleep(5)
        
        print("\n2. 停止1秒")
        robot.stop()
        time.sleep(1)
        
        print("\n3. 后退 200mm/s，持续3秒")
        robot.move_backward(speed=200)
        time.sleep(5)
        
        print("\n4. 停止1秒")
        robot.stop()
        time.sleep(1)
        
        print("\n5. 原地左转（逆时针）0.8rad/s，持续3秒")
        robot.rotate_left(speed=0.8)
        time.sleep(3)
        
        print("\n6. 停止1秒")
        robot.stop()
        time.sleep(3)
        
        print("\n7. 原地右转（顺时针）0.8rad/s，持续3秒")
        robot.rotate_right(speed=0.8)
        time.sleep(3)
        
        print("\n8. 停止")
        robot.stop()
        time.sleep(3)
        
        print("\n\n测试完成！")
        
    except KeyboardInterrupt:
        print("\n\n用户中断")
    finally:
        robot.stop()
        robot.disconnect()


def example_2_turn_and_move():
    """示例2: 转向+前进组合运动（模拟转弯）"""
    print("=" * 60)
    print("示例2: 履带底盘转弯运动")
    print("=" * 60)
    
    PORT = '/dev/ttyACM0'
    
    with WheeltecRobot(port=PORT, chassis_type='tracked') as robot:
        robot.start_receive(callback=status_callback)
        time.sleep(1)
        
        print("\n\n1. 前进同时左转（大半径转弯）")
        robot.set_velocity(vx=120, vz=0.4)  # 前进+转向
        time.sleep(3)
        
        print("\n2. 直行")
        robot.set_velocity(vx=150)
        time.sleep(2)
        
        print("\n3. 前进同时右转")
        robot.set_velocity(vx=120, vz=-0.4)
        time.sleep(3)
        
        print("\n4. 停止")
        robot.stop()
        
        print("\n\n测试完成！")


def example_3_precise_turn():
    """示例3: 精确转向（转向指定角度）"""
    print("=" * 60)
    print("示例3: 履带底盘精确转向")
    print("=" * 60)
    
    PORT = '/dev/ttyACM0'
    
    def turn_angle(robot, angle_deg, angular_speed=0.5):
        """
        转向指定角度
        
        Args:
            robot: 机器人对象
            angle_deg: 目标角度（度），正值逆时针，负值顺时针
            angular_speed: 角速度 (rad/s)
        """
        # 转换角度到弧度
        angle_rad = math.radians(abs(angle_deg))
        
        # 计算转向时间
        turn_time = angle_rad / abs(angular_speed)
        
        # 确定转向方向
        direction = 1 if angle_deg > 0 else -1
        
        print(f"  转向 {angle_deg}°，预计用时 {turn_time:.2f}秒")
        
        # 开始转向
        robot.set_velocity(vz=direction * angular_speed)
        time.sleep(turn_time)
        robot.stop()
        time.sleep(0.5)
    
    with WheeltecRobot(port=PORT, chassis_type='tracked') as robot:
        robot.start_receive(callback=status_callback)
        time.sleep(1)
        
        print("\n\n1. 左转90度")
        turn_angle(robot, 90, angular_speed=0.5)
        
        print("\n2. 前进1米")
        robot.move_forward(200)  # 200mm/s
        time.sleep(5)  # 5秒 = 1米
        robot.stop()
        time.sleep(0.5)
        
        print("\n3. 右转90度")
        turn_angle(robot, -90, angular_speed=0.5)
        
        print("\n4. 前进1米")
        robot.move_forward(200)
        time.sleep(5)
        robot.stop()
        
        print("\n\n方形路径完成！")


def example_4_obstacle_avoidance():
    """示例4: 简单避障（模拟传感器）"""
    print("=" * 60)
    print("示例4: 履带底盘避障行为")
    print("=" * 60)
    
    PORT = '/dev/ttyACM0'
    
    def simulate_obstacle_detected():
        """模拟障碍物检测（实际应用中从传感器读取）"""
        import random
        return random.random() < 0.3  # 30%概率检测到障碍
    
    with WheeltecRobot(port=PORT, chassis_type='tracked') as robot:
        robot.start_receive(callback=status_callback)
        time.sleep(1)
        
        print("\n\n开始避障演示（10秒）...")
        print("检测到障碍时会后退并转向\n")
        
        start_time = time.time()
        while time.time() - start_time < 10:
            if simulate_obstacle_detected():
                print("\n⚠️  检测到障碍！执行避障...")
                
                # 停止
                robot.stop()
                time.sleep(0.3)
                
                # 后退
                print("  1. 后退...")
                robot.move_backward(100)
                time.sleep(1)
                
                # 转向
                print("  2. 转向...")
                robot.rotate_left(0.6)
                time.sleep(1.5)
                
                # 停止
                robot.stop()
                print("  3. 继续前进")
            
            # 正常前进
            robot.move_forward(120)
            time.sleep(0.5)
        
        robot.stop()
        print("\n\n避障演示完成！")


def example_5_speed_control():
    """示例5: 速度渐变控制（平滑加减速）"""
    print("=" * 60)
    print("示例5: 履带底盘平滑加减速")
    print("=" * 60)
    
    PORT = '/dev/ttyACM0'
    
    def smooth_accelerate(robot, target_speed, duration=2.0, steps=20):
        """平滑加速到目标速度"""
        step_time = duration / steps
        for i in range(steps + 1):
            speed = target_speed * (i / steps)
            robot.set_velocity(vx=speed)
            time.sleep(step_time)
    
    def smooth_decelerate(robot, current_speed, duration=2.0, steps=20):
        """平滑减速到停止"""
        step_time = duration / steps
        for i in range(steps, -1, -1):
            speed = current_speed * (i / steps)
            robot.set_velocity(vx=speed)
            time.sleep(step_time)
    
    with WheeltecRobot(port=PORT, chassis_type='tracked') as robot:
        robot.start_receive(callback=status_callback)
        time.sleep(1)
        
        print("\n\n1. 平滑加速到200mm/s（2秒）")
        smooth_accelerate(robot, target_speed=200, duration=2.0)
        
        print("\n2. 保持速度3秒")
        time.sleep(3)
        
        print("\n3. 平滑减速到停止（2秒）")
        smooth_decelerate(robot, current_speed=200, duration=2.0)
        
        robot.stop()
        print("\n\n平滑控制完成！")


def example_6_patrol_mode():
    """示例6: 巡逻模式（矩形路径）"""
    print("=" * 60)
    print("示例6: 履带底盘巡逻模式")
    print("=" * 60)
    
    PORT = '/dev/ttyACM0'
    
    def turn_90_left(robot):
        """左转90度"""
        robot.rotate_left(0.5)
        time.sleep(math.pi / 2 / 0.5)  # 90度 = π/2弧度
        robot.stop()
        time.sleep(0.3)
    
    with WheeltecRobot(port=PORT, chassis_type='tracked') as robot:
        robot.start_receive(callback=status_callback)
        time.sleep(1)
        
        print("\n\n开始矩形巡逻（2圈）...")
        
        for lap in range(2):
            print(f"\n第 {lap + 1} 圈:")
            
            for side in range(4):
                print(f"  边 {side + 1}/4: 前进")
                robot.move_forward(150)
                time.sleep(3)  # 前进3秒
                
                robot.stop()
                time.sleep(0.3)
                
                if side < 3:  # 最后一边不转向
                    print(f"  转向")
                    turn_90_left(robot)
        
        robot.stop()
        print("\n\n巡逻完成！")


def example_7_battery_monitor():
    """示例7: 电池监控与低电量保护"""
    print("=" * 60)
    print("示例7: 履带底盘电池监控")
    print("=" * 60)
    
    PORT = '/dev/ttyACM0'
    
    # 电压阈值
    VOLTAGE_LOW = 11.0    # 低电量阈值
    VOLTAGE_CRITICAL = 10.8  # 严重低电量阈值
    
    def battery_check_callback(status: RobotStatus):
        """带电池检查的回调函数"""
        voltage = status.battery_voltage
        
        if voltage < VOLTAGE_CRITICAL:
            print(f"\n🔴 严重低电量: {voltage:.2f}V - 立即停止！")
            robot.stop()
            return 'critical'
        elif voltage < VOLTAGE_LOW:
            print(f"\n🟡 低电量警告: {voltage:.2f}V")
            return 'low'
        
        print(f"\r🟢 电压正常: {voltage:.2f}V | "
              f"速度: {status.velocity_x:6.1f}mm/s", end='')
        return 'ok'
    
    robot = WheeltecRobot(port=PORT, chassis_type='tracked')
    
    try:
        if not robot.connect():
            return
        
        robot.start_receive()
        time.sleep(1)
        
        print("\n\n开始运行（带电池监控）...")
        
        start_time = time.time()
        while time.time() - start_time < 30:  # 运行30秒
            # 检查电池
            status = robot.get_status()
            battery_status = battery_check_callback(status)
            
            if battery_status == 'critical':
                break
            
            # 正常运行
            robot.move_forward(100)
            time.sleep(0.5)
        
        robot.stop()
        print("\n\n监控结束")
        
    except KeyboardInterrupt:
        print("\n\n用户中断")
    finally:
        robot.stop()
        robot.disconnect()


def example_8_keyboard_control():
    """示例8: 键盘控制履带底盘"""
    print("=" * 60)
    print("示例8: 键盘控制履带底盘")
    print("=" * 60)
    
    try:
        from pynput import keyboard
    except ImportError:
        print("错误: 需要安装pynput库")
        print("运行: pip install pynput")
        return
    
    PORT = '/dev/ttyACM0'
    
    robot = WheeltecRobot(port=PORT, chassis_type='tracked')
    
    if not robot.connect():
        return
    
    robot.start_receive(callback=status_callback)
    time.sleep(1)
    
    print("\n\n履带底盘键盘控制说明:")
    print("  W/w    - 前进")
    print("  S/s    - 后退")
    print("  A/a    - 原地左转")
    print("  D/d    - 原地右转")
    print("  Q/q    - 前进+左转")
    print("  E/e    - 前进+右转")
    print("  空格   - 停止")
    print("  ESC    - 退出")
    print("\n开始控制...\n")
    
    # 速度参数
    LINEAR_SPEED = 150  # mm/s
    ANGULAR_SPEED = 0.6  # rad/s
    TURN_ANGULAR = 0.3  # 转弯时的角速度
    
    def on_press(key):
        try:
            if hasattr(key, 'char'):
                if key.char == 'w' or key.char == 'W':
                    robot.move_forward(LINEAR_SPEED)
                elif key.char == 's' or key.char == 'S':
                    robot.move_backward(LINEAR_SPEED)
                elif key.char == 'a' or key.char == 'A':
                    robot.rotate_left(ANGULAR_SPEED)
                elif key.char == 'd' or key.char == 'D':
                    robot.rotate_right(ANGULAR_SPEED)
                elif key.char == 'q' or key.char == 'Q':
                    # 前进+左转
                    robot.set_velocity(vx=LINEAR_SPEED, vz=TURN_ANGULAR)
                elif key.char == 'e' or key.char == 'E':
                    # 前进+右转
                    robot.set_velocity(vx=LINEAR_SPEED, vz=-TURN_ANGULAR)
        except AttributeError:
            if key == keyboard.Key.space:
                robot.stop()
            elif key == keyboard.Key.esc:
                print("\n\n退出控制")
                return False
    
    def on_release(key):
        # 松开按键时停止
        robot.stop()
    
    # 监听键盘
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()
    
    robot.disconnect()


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print(" WHEELTEC履带底盘控制库 - 使用示例")
    print("=" * 60)
    
    # 列出可用串口
    print("\n检测可用串口设备:")
    list_serial_ports()
    
    print("\n" + "=" * 60)
    print("履带底盘特点:")
    print("  ✓ 前后移动（X轴）")
    print("  ✓ 原地转向（Z轴）")
    print("  ✓ 组合运动（前进+转向 = 转弯）")
    print("  ✗ 不支持左右平移（Y轴）")
    print("=" * 60)
    
    print("\n请选择要运行的示例:")
    print("  1 - 基本控制（前进、后退、转向）")
    print("  2 - 转弯运动（前进+转向组合）")
    print("  3 - 精确转向（指定角度）")
    print("  4 - 避障行为")
    print("  5 - 平滑加减速")
    print("  6 - 巡逻模式（矩形路径）")
    print("  7 - 电池监控")
    print("  8 - 键盘控制")
    print("  0 - 退出")
    print("=" * 60)
    
    choice = input("\n请输入选项 (0-8): ")
    
    if choice == '1':
        example_1_basic_tracked_control()
    elif choice == '2':
        example_2_turn_and_move()
    elif choice == '3':
        example_3_precise_turn()
    elif choice == '4':
        example_4_obstacle_avoidance()
    elif choice == '5':
        example_5_speed_control()
    elif choice == '6':
        example_6_patrol_mode()
    elif choice == '7':
        example_7_battery_monitor()
    elif choice == '8':
        example_8_keyboard_control()
    elif choice == '0':
        print("退出")
    else:
        print("无效选项")


if __name__ == "__main__":
    main()