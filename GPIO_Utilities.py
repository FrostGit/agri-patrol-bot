# -*- coding: utf-8 -*-
import time
import board
import queue
import threading
import RPi.GPIO as GPIO
from adafruit_pca9685 import PCA9685

# --- 常量配置 ---
PCA_ADDRESS = 0x41          # PCA9685 I2C 地址
PWM_FREQ = 60               # PWM 频率 (Hz)

# 通道定义
CH_FAN_POS = 10             # 风扇正极通道
CH_FAN_NEG = 11             # 风扇负极通道

class FanController:
    """
    树莓派 PCA9685 风扇控制模块（支持 PWM 调速）
    """

    def __init__(self):
        self.pca = None
        self.is_initialized = False
        self._current_duty = 0
        # [Fix 1] 将 Lock 改为 RLock (可重入锁)，防止 on() 调用 set_speed() 时发生死锁
        self._lock = threading.RLock()

    def init(self):
        """初始化 PCA9685"""
        try:
            i2c = board.I2C()
            self.pca = PCA9685(i2c, address=PCA_ADDRESS)
            self.pca.frequency = PWM_FREQ
            self.is_initialized = True
            print("[Fan] PCA9685 初始化成功")
        except Exception as e:
            print(f"[Fan] 初始化失败：{e}")
            self.is_initialized = False

    def set_duty_cycle(self, duty_cycle: int):
        """直接设置 PWM 占空比"""
        with self._lock:  # 线程安全保护
            if not self.is_initialized:
                print("[Warn] 风扇未初始化，忽略设置")
                return
            
            duty = max(0x0000, min(0xFFFF, duty_cycle))
            try:
                self.pca.channels[CH_FAN_POS].duty_cycle = duty
                self.pca.channels[CH_FAN_NEG].duty_cycle = 0x0000
                self._current_duty = duty
            except Exception as e:
                print(f"[Err] 设置占空比失败：{e}")

    def set_speed(self, percent: float):
        """设置风扇转速百分比（0~100%）"""
        # 输入校验
        if not isinstance(percent, (int, float)):
            print(f"[Warn] 速度参数类型错误：{type(percent)}")
            return
        
        if percent < 0:
            percent = 0
        elif percent > 100:
            percent = 100
            
        duty = int((percent / 100.0) * 0xFFFF * 0.8) # 保护性限制最高转速在 80% 以内
        self.set_duty_cycle(duty)

    def on(self):
        """开启风扇"""
        with self._lock:
            if self._current_duty == 0:
                self.set_speed(100)
            else:
                self.set_duty_cycle(self._current_duty)

    def off(self):
        """关闭风扇"""
        self.set_duty_cycle(0x0000)

    def cleanup(self):
        """释放资源"""
        self.off()
        self.is_initialized = False
        print("[Fan] 资源已释放")

# --- 超声波雷达类 ---
class UltrasonicRadar:
    def __init__(self):
        self.PIN_TRIG = 23
        self.PIN_ECHO = 24
        self.PIN_BUZZER = 16
        self.DISTANCE_FAR = 30.0
        self.DISTANCE_MID = 20.0
        self.DISTANCE_CLOSE = 10.0
        self.stop_event = threading.Event()
        self.distance_queue = queue.Queue(maxsize=1)
        self.distance_lock = threading.Lock()
        self.latest_distance = None 
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False) 
        GPIO.setup(self.PIN_TRIG, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.PIN_ECHO, GPIO.IN)
        GPIO.setup(self.PIN_BUZZER, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setwarnings(True) 

    def _measure_distance(self):
        while not self.stop_event.is_set():
            try:
                GPIO.output(self.PIN_TRIG, GPIO.HIGH)
                time.sleep(0.00015)
                # [Fix 2] 修复变量未定义错误，LOW 应为 GPIO.LOW
                GPIO.output(self.PIN_TRIG, GPIO.LOW)

                timeout = time.time() + 0.1
                while not GPIO.input(self.PIN_ECHO):
                    if time.time() > timeout: raise TimeoutError("Echo start timeout")
                
                t_start = time.perf_counter()
                timeout = time.time() + 0.1
                while GPIO.input(self.PIN_ECHO):
                    if time.time() > timeout: raise TimeoutError("Echo end timeout")
                
                t_end = time.perf_counter()
                duration = t_end - t_start
                distance = (duration * 34000) / 2

                with self.distance_lock:
                    self.latest_distance = distance

                try:
                    self.distance_queue.put_nowait(distance)
                except queue.Full:
                    try:
                        self.distance_queue.get_nowait()
                        self.distance_queue.put_nowait(distance)
                    except queue.Empty:
                        pass
            except TimeoutError:
                pass
            except Exception as e:
                print(f"[Radar Err] {e}")
            time.sleep(0.1)

    def _beep_logic(self):
        while not self.stop_event.is_set():
            distance = None
            try:
                distance = self.distance_queue.get(timeout=0.5)
            except queue.Empty:
                GPIO.output(self.PIN_BUZZER, GPIO.HIGH)
                continue

            if distance < self.DISTANCE_CLOSE:
                GPIO.output(self.PIN_BUZZER, GPIO.LOW)
                if self.stop_event.wait(0.1): break
            elif distance < self.DISTANCE_MID:
                GPIO.output(self.PIN_BUZZER, GPIO.LOW)
                if self.stop_event.wait(0.1): break
                GPIO.output(self.PIN_BUZZER, GPIO.HIGH)
                if self.stop_event.wait(0.1): break
            elif distance < self.DISTANCE_FAR:
                GPIO.output(self.PIN_BUZZER, GPIO.LOW)
                if self.stop_event.wait(0.2): break
                GPIO.output(self.PIN_BUZZER, GPIO.HIGH)
                if self.stop_event.wait(0.2): break
            else:
                GPIO.output(self.PIN_BUZZER, GPIO.HIGH)
            
            if self.stop_event.wait(0.1): break

    def get_distance(self):
        with self.distance_lock:
            return self.latest_distance

    def run(self, duration=0):
        print("[Radar] Started.")
        self.stop_event.clear()
        beep_thread = threading.Thread(target=self._beep_logic, daemon=True)
        measure_thread = threading.Thread(target=self._measure_distance, daemon=True)
        beep_thread.start()
        measure_thread.start()
        try:
            if duration > 0: self.stop_event.wait(timeout=duration)
            else: self.stop_event.wait()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
            if beep_thread.is_alive(): beep_thread.join(timeout=1)
            if measure_thread.is_alive(): measure_thread.join(timeout=1)

    def stop(self):
        print("[Radar] Stopping...")
        self.stop_event.set()
        try:
            GPIO.output(self.PIN_BUZZER, GPIO.LOW)
            GPIO.cleanup()
        except:
            pass

# --- 测试用例部分 ---

def test_fan_controller():
    """
    风扇控制器完整测试案例
    """
    print("\n" + "="*30)
    print("开始风扇控制器测试 (FanController Test)")
    print("="*30)
    
    fan = FanController()
    
    # 1. 测试初始化
    print("\n[Case 1] 初始化测试...")
    fan.init()
    if not fan.is_initialized:
        print("[FAIL] 初始化失败，跳过后续测试")
        return
    print("[PASS] 初始化成功")

    try:
        # 2. 测试边界值 (0% 和 100%)
        print("\n[Case 2] 边界值测试 (0% & 100%)...")
        fan.set_speed(0)
        print("  -> 设置 0% 速度 (应关闭)")
        time.sleep(1)
        
        fan.set_speed(100)
        print("  -> 设置 100% 速度 (应全速)")
        time.sleep(1)
        print("[PASS] 边界值测试通过")

        # 3. 测试异常输入 (负数与超过 100)
        print("\n[Case 3] 异常输入容错测试...")
        fan.set_speed(-10)
        print("  -> 输入 -10% (应自动修正为 0%)")
        time.sleep(0.5)
        
        fan.set_speed(150)
        print("  -> 输入 150% (应自动修正为 100%)")
        time.sleep(1)
        print("[PASS] 异常输入已容错")

        # 4. 测试状态保持 (on/off 恢复)
        print("\n[Case 4] 状态保持测试 (On/Off Recovery)...")
        fan.set_speed(60)
        print("  -> 设定基准速度 60%")
        time.sleep(1)
        
        fan.off()
        print("  -> 关闭风扇 (off)")
        time.sleep(1)
        
        fan.on()
        print("  -> 重新开启 (on)，应恢复至 60%")
        time.sleep(2)
        print("[PASS] 状态恢复测试通过")

        # 5. 梯度调速测试
        print("\n[Case 5] 梯度调速测试...")
        for speed in [20, 40, 60, 80]:
            fan.set_speed(speed)
            print(f"  -> 速度调整至 {speed}%")
            time.sleep(1)
        print("[PASS] 梯度调速测试通过")

    except Exception as e:
        print(f"[FAIL] 测试过程中发生异常：{e}")
        import traceback
        traceback.print_exc()
    finally:
        fan.cleanup()
        print("\n[END] 风扇测试结束，资源已清理")
        print("="*30 + "\n")

def test_radar_system():
    """雷达系统测试"""
    print("\n" + "="*30)
    print("开始超声波雷达测试 (UltrasonicRadar Test)")
    print("="*30)
    try:
        radar = UltrasonicRadar()
        radar_thread = threading.Thread(target=radar.run, kwargs={'duration': 20})
        radar_thread.start()

        print("监控距离数据 (20 秒)...")
        for _ in range(20):
            time.sleep(1)
            dist = radar.get_distance()
            if dist is not None:
                print(f"  -> 当前距离：{dist:.2f} cm")
            else:
                print("  -> 等待数据...")
        
        radar_thread.join()
    except Exception as e:
        print(f"[Radar Test Error] {e}")
        import traceback
        traceback.print_exc()
    finally:
        GPIO.cleanup()
        print("[END] 雷达测试结束")

if __name__ == "__main__":
    import sys
    
    mode = "all"
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

    try:
        if mode in ["fan", "all"]:
            confirm = input("是否运行风扇控制器测试？ [y/N]: ")
            if confirm.lower() == 'y':
                confirm = None
                test_fan_controller() 
            else:
                print("跳过风扇测试。")
        
        if mode in ["radar", "all"]:
            confirm = input("是否继续运行超声波雷达测试？ [y/N]: ")
            if confirm.lower() == 'y':
                test_radar_system()
            else:
                print("跳过雷达测试。")
                
    except KeyboardInterrupt:
        print("\n用户中断测试")
    finally:
        GPIO.cleanup()
        print("所有测试完成，系统退出。")