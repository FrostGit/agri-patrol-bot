import threading
import queue
import time
import RPi.GPIO as GPIO

class UltrasonicRadar:
    def __init__(self):
        # 引脚定义
        self.PIN_TRIG = 23
        self.PIN_ECHO = 24
        self.PIN_BUZZER = 16

        # 距离阈值 (cm)
        self.DISTANCE_FAR = 30.0
        self.DISTANCE_MID = 20.0
        self.DISTANCE_CLOSE = 10.0

        # 控制信号
        self.stop_event = threading.Event()
        # 内部通信用队列 (仅供蜂鸣器线程消费)
        self.distance_queue = queue.Queue(maxsize=1)
        
        # 用于外部获取的线程安全共享数据
        self.distance_lock = threading.Lock()
        self.latest_distance = None 

        # GPIO 初始化
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False) 
        GPIO.setup(self.PIN_TRIG, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.PIN_ECHO, GPIO.IN)
        GPIO.setup(self.PIN_BUZZER, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setwarnings(True) 


    def _measure_distance(self):
        """测距线程任务"""
        while not self.stop_event.is_set():
            try:
                # 发送触发信号
                GPIO.output(self.PIN_TRIG, GPIO.HIGH)
                time.sleep(0.00015) # 150us
                GPIO.output(self.PIN_TRIG, GPIO.LOW)

                # 等待回声开始 (带超时)
                timeout = time.time() + 0.1 # 100ms 超时
                while not GPIO.input(self.PIN_ECHO):
                    if time.time() > timeout:
                        raise TimeoutError("Echo start timeout")
                
                t_start = time.perf_counter()

                # 等待回声结束 (带超时)
                timeout = time.time() + 0.1
                while GPIO.input(self.PIN_ECHO):
                    if time.time() > timeout:
                        raise TimeoutError("Echo end timeout")
                
                t_end = time.perf_counter()

                # 计算距离 (声速 34000 cm/s)
                duration = t_end - t_start
                distance = (duration * 34000) / 2

                #  更新共享变量 (线程安全)
                with self.distance_lock:
                    self.latest_distance = distance

                # 放入队列 (供蜂鸣器线程消费)
                try:
                    self.distance_queue.put_nowait(distance)
                except queue.Full:
                    try:
                        self.distance_queue.get_nowait()
                        self.distance_queue.put_nowait(distance)
                    except queue.Empty:
                        pass

                # 调试打印
                # print(f"Measure: {distance:.2f} cm")

            except TimeoutError:
                print("[WARN]--Measurement timeout. No echo received.")
                pass
            except Exception as e:
                print(f"[ERR]--Measure error: {e}")
            
            time.sleep(0.1)

    def _beep_logic(self):
        """蜂鸣器报警线程任务"""
        while not self.stop_event.is_set():
            distance = None
            try:
                # 蜂鸣器线程从队列获取数据，确保每次测量周期只处理一次
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
        """
        供外部调用方获取当前最新距离。
        返回：float (cm) 或 None (如果尚未测量)
        """
        with self.distance_lock:
            return self.latest_distance

    def run(self, duration=0):
        """启动雷达"""
        print("Ultrasonic radar started. Press Ctrl+C to stop.")
        self.stop_event.clear()
        
        beep_thread = threading.Thread(target=self._beep_logic, daemon=True)
        measure_thread = threading.Thread(target=self._measure_distance, daemon=True)

        beep_thread.start()
        measure_thread.start()

        try:
            if duration > 0:
                self.stop_event.wait(timeout=duration)
            else:
                self.stop_event.wait()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
            # 守护线程通常不需要 join，但为了资源清理明确等待一下
            if beep_thread.is_alive(): beep_thread.join(timeout=1)
            if measure_thread.is_alive(): measure_thread.join(timeout=1)

    def stop(self):
        """停止雷达"""
        print("Stopping radar...")
        self.stop_event.set()
        try:
            GPIO.output(self.PIN_BUZZER, GPIO.LOW)
            GPIO.cleanup()
        except:
            pass

if __name__ == "__main__":
    try:
        radar = UltrasonicRadar()
        # 启动雷达线程 (非阻塞，因为内部线程是 daemon 且 run 中有 wait)
        # 为了演示外部获取，我们在另一个线程启动 run，或者利用 run 的等待时间
        # 这里为了演示方便，我们启动 run 在一个单独线程，主线程用来打印距离
        
        radar_thread = threading.Thread(target=radar.run, kwargs={'duration': 10}) # 运行 10 秒
        radar_thread.start()

        print("Monitoring distance from main thread...")
        for _ in range(10):
            time.sleep(1)
            # 调用方获取距离
            dist = radar.get_distance()
            if dist is not None:
                print(f"[Main Thread] Current Distance: {dist:.2f} cm")
            else:
                print("[Main Thread] Waiting for data...")
        
        radar_thread.join()

    except Exception as e:
        print(f"System error: {e}")
    finally:
        GPIO.cleanup()