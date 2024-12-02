import sys
import os
import random
import math
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QGridLayout, QWidget, QComboBox, QSpinBox, QSizePolicy, QMessageBox
)
from PySide2.QtGui import QColor, QPainter, QPen, QBrush, QFont, QIcon
from PySide2.QtCore import Qt, QTimer, QTime, Signal
import pygame
import csv
from datetime import datetime

class WheelWidget(QWidget):
    iteration_time_decided = Signal(float)  # Signal to emit the iteration time when animation finishes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rotation_angle = 0.0 # 目前的旋轉角度，初始為 0.0
        self.is_animating = False # 表示動畫是否正在進行，初始為 False
        self.timer = QTimer() # 使用 QTimer 控制動畫更新。
        self.timer.timeout.connect(self.update_animation)
        self.animation_duration = 1000  # 動畫的總時長，單位為毫秒（預設為 1000 毫秒，1 秒）。
        self.elapsed_time = 0 # 動畫運行的累積時間。
        self.start_speed = random.uniform(2000, 4000)  # 起始速度，隨機生成一個範圍內的值（720 至 1080 度/秒）。
        self.current_speed = self.start_speed # 當前速度，初始化為起始速度。
        self.rotation_angles = [] # 儲存動畫每幀的角度變化量。
        self.current_frame = 0 # 分別表示當前幀數和總幀數。
        self.total_frames = 0
        self.current_text = ""  # Current displayed text

        # Deceleration exponent 減速曲線的指數值（默認為 2.0，平方減速）。
        self.exponent = 2.0

        # For mapping angle to iteration time
        self.lower_limit = 5.0  # Default lower limit in seconds
        self.upper_limit = 50.0  # Default upper limit in seconds

        # UI Label for displaying time
        self.text_label = QLabel("0.0s", self)
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setFont(QFont("Arial", 40))
        self.text_label.setStyleSheet("border: 5px solid black; padding: 10px;")
        self.setMaximumSize(200, 100)  # 限制最大寬度和高度為 300x300

        layout = QVBoxLayout(self)
        layout.addWidget(self.text_label)

    def start_animation(self):
        self.is_animating = True
        self.elapsed_time = 0
        self.current_frame = 0
        self.start_speed = random.uniform(2000, 4000)  # Random starting speed
        self.current_speed = self.start_speed
        self.rotation_angle = 0.0

        # Prepare the list of rotation angles
        frame_interval = 1  # milliseconds (approx 60 FPS)
        self.total_frames = self.animation_duration // frame_interval

        # Calculate the intervals (angles per frame)
        progress_list = [(i / (self.total_frames - 1)) for i in range(self.total_frames)]
        self.rotation_angles = []
        for p in progress_list:
            # Use deceleration curve
            speed = self.start_speed * (1 - p ** self.exponent)
            delta_angle = speed * frame_interval / 1000.0
            self.rotation_angles.append(delta_angle)

        self.timer.start(frame_interval)

    def update_animation(self):
        if not self.is_animating:
            return

        if self.current_frame >= self.total_frames:
            self.timer.stop()
            self.is_animating = False
            self.rotation_angle %= 360
            # Map the final angle to iteration time
            angle = self.rotation_angle % 360
            proportion = angle / 360.0
            iteration_time = self.lower_limit + (self.upper_limit - self.lower_limit) * proportion
            self.iteration_time_decided.emit(iteration_time)
            self.text_label.setText(f"{iteration_time:.1f}s")
            return

        # Update displayed text during animation
        angle = (self.rotation_angle + self.rotation_angles[self.current_frame]) % 360
        proportion = angle / 360.0
        current_time = self.lower_limit + (self.upper_limit - self.lower_limit) * proportion
        self.text_label.setText(f"{current_time:.1f}s")

        # Update rotation
        self.rotation_angle += self.rotation_angles[self.current_frame]
        self.current_frame += 1

    def set_limits(self, lower, upper):
        self.lower_limit = lower
        self.upper_limit = upper

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        painter.setRenderHint(QPainter.Antialiasing)

        painter.setPen(QPen(Qt.black, 2))
        painter.setBrush(QBrush(Qt.white))

class RouletteApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rontgen Roulette")
        self.setGeometry(100, 100, 200, 200)

        # Initialize variables
        self.rewards_folder = "rewards"
        self.rewards = {}
        self.current_reward = None
        self.winner_records = {}
        self.load_rewards()
        self.init_ui()
        self.highlighting_winner = False  # 新增布林變數

        # 新增屬性以處理結果儲存
        self.result_file = None  # 儲存抽獎結果的檔案路徑
        self.file_initialized = False  # 是否已經初始化檔案

        # Initialize pygame for sound effects
        pygame.mixer.init()
        self.rolling_sound = pygame.mixer.Sound("resources/rolling_sound.wav")
        self.rolling_sound.set_volume(0.5)
        self.sound_channel = pygame.mixer.Channel(0)
        
    def _generate_result_file_name(self):
        """生成不覆蓋舊檔的檔名，格式為 '得獎名單_YYYYMMDD_HHMMSS.csv'"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"得獎名單_{timestamp}.csv"

    def _initialize_result_file(self):
        """初始化結果檔案，在第一次抽獎時呼叫"""
        if not self.file_initialized:
            self.result_file = self._generate_result_file_name()
            # 創建檔案並寫入標題行
            with open(self.result_file, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file, delimiter=",")
                writer.writerow(["員工姓名", "獎項"])
            self.file_initialized = True

    def _save_results_to_file(self, winners):
        """將中獎結果寫入檔案"""
        if not self.file_initialized:
            self._initialize_result_file()
        # 將中獎者寫入檔案
        with open(self.result_file, "a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file, delimiter=",")
            for winner in winners:
                writer.writerow([winner, self.current_reward])
                
    def load_rewards(self):
        """Load prize lists from txt files in rewards folder."""
        for file in os.listdir(self.rewards_folder):
            if file.endswith(".txt"):
                prize_name = os.path.splitext(file)[0]
                with open(os.path.join(self.rewards_folder, file), "r", encoding="utf-8") as f:
                    self.rewards[prize_name] = f.read().splitlines()

    def init_ui(self):
        """Initialize UI components."""
        self.setWindowIcon(QIcon("resources/icon.png"))
        font_size = 20  # 統一字體大小

        def set_font(widget, size):
            """Helper function to set font size for a widget."""
            font = widget.font()
            font.setPointSize(size)
            widget.setFont(font)

        main_layout = QVBoxLayout()

        # Reward selection layout
        reward_layout = QHBoxLayout()
        self.reward_label = QLabel("當前獎項:")
        set_font(self.reward_label, font_size)
        self.reward_combo = QComboBox()
        set_font(self.reward_combo, font_size)
        self.reward_combo.addItems(self.rewards.keys())
        self.reward_combo.currentIndexChanged.connect(self.update_reward)
        reward_layout.addWidget(self.reward_label)
        reward_layout.addWidget(self.reward_combo)

        # Pick number selection (1-5)
        self.pick_label = QLabel("單抽人數:")
        set_font(self.pick_label, font_size)
        self.pick_spinner = QSpinBox()
        set_font(self.pick_spinner, font_size)
        self.pick_spinner.setRange(1, 50)
        reward_layout.addWidget(self.pick_label)
        reward_layout.addWidget(self.pick_spinner)

        # Mode selection
        self.mode_label = QLabel("模式:")
        set_font(self.mode_label, font_size)
        self.mode_combo = QComboBox()
        set_font(self.mode_combo, font_size)
        # 新增 "AI部門" 選項
        self.mode_combo.addItems(["隨機歷遍", "循序歷遍", "AI部門"])
        self.mode_combo.currentIndexChanged.connect(self.update_mode)
        reward_layout.addWidget(self.mode_label)
        reward_layout.addWidget(self.mode_combo)

        # Iteration time range (seconds)
        self.duration_label = QLabel("歷遍時間範圍(秒):")
        set_font(self.duration_label, font_size)
        self.duration_lower_spinner = QSpinBox()
        set_font(self.duration_lower_spinner, font_size)
        self.duration_lower_spinner.setRange(1, 50)
        self.duration_lower_spinner.setValue(3)
        self.duration_upper_spinner = QSpinBox()
        set_font(self.duration_upper_spinner, font_size)
        self.duration_upper_spinner.setRange(1, 500)
        self.duration_upper_spinner.setValue(10)
        self.to_babel = QLabel("至")
        set_font(self.to_babel, font_size)
        reward_layout.addWidget(self.duration_label)
        reward_layout.addWidget(self.duration_lower_spinner)

        reward_layout.addWidget(self.to_babel)
        reward_layout.addWidget(self.duration_upper_spinner)

        # Starting interval time (milliseconds), default 500ms
        self.start_interval_label = QLabel("起始間隔(ms):")
        set_font(self.start_interval_label, font_size)
        self.start_interval_spinner = QSpinBox()
        set_font(self.start_interval_spinner, font_size)
        self.start_interval_spinner.setRange(1, 5000)
        self.start_interval_spinner.setValue(100)  # Default 500 ms
        reward_layout.addWidget(self.start_interval_label)
        reward_layout.addWidget(self.start_interval_spinner)

        # Final interval time (milliseconds), default 2000ms
        self.final_interval_label = QLabel("最終間隔(ms):")
        set_font(self.final_interval_label, font_size)
        self.final_interval_spinner = QSpinBox()
        set_font(self.final_interval_spinner, font_size)
        self.final_interval_spinner.setRange(100, 5000)
        self.final_interval_spinner.setValue(500)  # Default 2000 ms
        reward_layout.addWidget(self.final_interval_label)
        reward_layout.addWidget(self.final_interval_spinner)

        main_layout.addLayout(reward_layout)

        # 創建水平佈局
        horizontal_layout = QHBoxLayout()
        # 添加獎項顯示標籤
        self.prize_label = QLabel("本次獎項：")
        self.prize_label.setAlignment(Qt.AlignCenter)
        set_font(self.prize_label, font_size + 12)  # 標籤字體略大
        self.prize_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        horizontal_layout.addWidget(self.prize_label, stretch=2)
        
        # 添加 WheelWidget
        self.wheel_widget = WheelWidget()
        self.wheel_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        horizontal_layout.addWidget(self.wheel_widget, stretch=1)

        # 將水平佈局添加到主佈局
        main_layout.addLayout(horizontal_layout, stretch=1)

        # Winner grid layout
        self.winner_grid_layout = QGridLayout()
        self.winner_grid_widget = QWidget()
        self.winner_grid_widget.setLayout(self.winner_grid_layout)
        self.winner_grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.winner_grid_widget, stretch=2)
                
        # PULL button
        self.pull_button = QPushButton("抽獎開始!")
        set_font(self.pull_button, 80)
        self.pull_button.clicked.connect(self.start_lottery)
        self.pull_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        main_layout.addWidget(self.pull_button)

        # Employee grid
        self.grid_layout = QGridLayout()
        self.grid_widget = QWidget()
        self.grid_widget.setLayout(self.grid_layout)
        self.grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.grid_widget, stretch=4)

        # Set main layout
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.wheel_widget.iteration_time_decided.connect(self.wheel_animation_finished)
        self.update_reward()

    def update_reward(self):
        """Update current reward and employee pool."""
        self.current_reward = self.reward_combo.currentText()
        # 更新 prize_label 的顯示文字，顯示目前選定的獎項

        if self.mode_combo.currentText() == "AI部門":
            self.prize_label.setText(f"本次獎項：{self.current_reward}\n紅色:五獎*2 | 橙色:四獎*2 | 黃色:三獎*2 | 綠色:二獎*2 | 藍色:一獎*1")
        else:
            self.prize_label.setText(f"本次獎項：{self.current_reward}")
        
        # 清空 winner_indices，避免舊獎項索引干擾新獎項
        self.winner_indices = []

        # Initialize winner records for this reward if not already
        if self.current_reward not in self.winner_records:
            self.winner_records[self.current_reward] = []
        self.populate_employee_grid()
        self.update_winner_label()

    def update_mode(self):
        if self.mode_combo.currentText() == "AI部門":
            self.prize_label.setText(f"本次獎項：{self.current_reward}\n紅色:五獎*2 | 橙色:四獎*2 | 黃色:三獎*2 | 綠色:二獎*2 | 藍色:一獎*1")
        else:
            self.prize_label.setText(f"本次獎項：{self.current_reward}")  

    def populate_winner_grid(self):
        """Populate the winner grid with the current reward's winners."""
        # Clear existing grid
        for i in reversed(range(self.winner_grid_layout.count())):
            widget = self.winner_grid_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Get the winners for the current reward
        winners = self.winner_records.get(self.current_reward, [])
        num_winners = len(winners)

        # If no winners, do nothing
        if num_winners == 0:
            return

        # Define fixed grid size
        grid_width = 220  # Fixed width for each grid
        grid_height = 80  # Fixed height for each grid

        cols = 8  # Fixed number of columns
        rows = (num_winners + cols - 1) // cols  # Calculate number of rows

        # 取得當前模式
        mode = self.mode_combo.currentText()
        # 定義彩虹顏色列表
        rainbow_colors = [
            "#FF0000",  # Red
            "#FFA500",  # Orange
            "#FFFF00",  # Yellow
            "#008000",  # Green
            "#2F67D7",  # Blue
            "#8E3AC6",  # Indigo
            "#EE82EE",  # Violet
        ]

        for index, winner in enumerate(winners):
            row = index // cols
            col = index % cols

            # Create QLabel for winner name
            label = QLabel(winner)
            label.setAlignment(Qt.AlignCenter)
            label.setFixedSize(grid_width, grid_height)

            # Set font size for the winner name
            font = label.font()
            font.setPointSize(40)  # Adjust font size
            label.setFont(font)

            # Set background and border styles
            if mode == "AI部門":
                color_index = (index // 2) % len(rainbow_colors)
                background_color = rainbow_colors[color_index]
                label.setStyleSheet(f"background-color: {background_color}; border: 3px solid black; padding: 2px;")
            else:
                label.setStyleSheet("background-color: yellow; border: 3px solid black; padding: 2px;")

            self.winner_grid_layout.addWidget(label, row, col)

    def populate_employee_grid(self):
        """Populate the employee grid based on the current reward."""
        # Clear existing grid
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        employees = self.rewards[self.current_reward]
        num_employees = len(employees)
        if num_employees < 16 :
            oneCols = 5
        elif num_employees < 22 :
            oneCols = 7 
        else:
            oneCols = 10
        
        
        cols = min(oneCols, num_employees)  # Up to 10 columns
        rows = (num_employees + cols - 1) // cols

        for index, employee in enumerate(employees):
            row = index // cols
            col = index % cols

            # Create QLabel for employee name
            label = QLabel(employee)
            label.setAlignment(Qt.AlignCenter)
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

            # Dynamically set font size based on grid size
            font = label.font()
            # Calculate font size as a proportion of grid height (adjust multiplier as needed)
            cell_width = self.grid_widget.width() // cols
            cell_height = self.grid_widget.height() // rows
            dynamic_font_size = max(int(min(cell_width, cell_height) * 0.2), 25)  # Adjust 0.2 for scaling

            font.setPointSize(dynamic_font_size)
            label.setFont(font)

            # Set background and border styles
            if employee in self.winner_records[self.current_reward]:
                label.setStyleSheet("background-color: yellow; border: 2px solid black; padding: 5px;")
            else:
                label.setStyleSheet("border: 1px solid black; padding: 5px;")

            self.grid_layout.addWidget(label, row, col)

    def start_lottery(self):
        """Start the lottery drawing."""
        # 如果有高亮的中獎者，先將其轉為黃色
        if self.highlighting_winner:
            self.highlight_winners_to_yellow()

        # 禁用 PULL 按鈕
        self.pull_button.setEnabled(False)
        # 開始新的抽獎
        lower_limit = self.duration_lower_spinner.value()
        upper_limit = self.duration_upper_spinner.value()
        if lower_limit > upper_limit:
            lower_limit, upper_limit = upper_limit, lower_limit
        self.wheel_widget.set_limits(lower_limit, upper_limit)
        self.wheel_widget.start_animation()
        
    def highlight_winners_to_yellow(self):
        """將當次的紅色高亮切換為黃色高亮。"""
        for idx in self.winner_indices:
            widget_item = self.grid_layout.itemAt(idx)
            if widget_item:  # 確保 widget_item 存在
                widget = widget_item.widget()
                if widget:  # 確保 widget 存在
                    widget.setStyleSheet("background-color: yellow; border: 2px solid black; padding: 5px;")
        self.highlighting_winner = False  # 標記為高亮結束
     
    def wheel_animation_finished(self, iteration_time):
        """Slot called when the wheel animation finishes."""
        self.total_duration = iteration_time
        self.statusBar().showMessage(f"本次歷遍時間: {iteration_time:.1f} 秒")

        self.start_lottery_with_iteration_time(iteration_time)

    def start_lottery_with_iteration_time(self, iteration_time):
        """Start the lottery with the given iteration time."""
        employees = self.rewards[self.current_reward]
        pick_count = self.pick_spinner.value()
        mode = self.mode_combo.currentText()
        total_duration = iteration_time  # Use the iteration time from the wheel

        # Get starting and final intervals in milliseconds
        start_interval_ms = self.start_interval_spinner.value()
        final_interval_ms = self.final_interval_spinner.value()

        # Validate pick_count
        available_employees = [e for e in employees if e not in self.winner_records[self.current_reward]]
        if pick_count > len(available_employees):
            pick_count = len(available_employees)
            self.pick_spinner.setValue(pick_count)

        # Initialize variables for the lottery
        self.frame_count = 0
        self.total_frames = 0
        self.current_indices = []
        self.winner_indices = []  # 清空舊的中獎索引
        self.available_indices = [i for i in range(len(employees)) if employees[i] not in self.winner_records[self.current_reward]]

        # Calculate intervals
        self.intervals = self.calculate_intervals(total_duration, start_interval_ms, final_interval_ms)

        # For sequential iteration mode, start from a random position
        if mode == "循序歷遍":
            if len(self.available_indices) == 0:
                return
            self.seq_index = random.randint(0, len(self.available_indices) - 1)

        # Start the timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_lights)
        self.timer.start(self.intervals[0])  # Start with the first interval

    def calculate_intervals(self, total_duration, start_interval_ms, final_interval_ms):
        """Calculate intervals for the timer to create a slowing down effect."""
        exponent = 2  # Adjust the exponent to control the deceleration curve

        # Number of frames is variable, we need to solve for it so that the total duration matches
        # Let's assume N intervals, and calculate total duration as sum of intervals

        # Define a function to calculate the total duration based on N
        def total_time(N):
            if N <= 1:
                return start_interval_ms / 1000.0
            progress_list = [(i / (N - 1)) for i in range(N)]
            intervals = [start_interval_ms + (final_interval_ms - start_interval_ms) * (p ** exponent) for p in progress_list]
            return sum(intervals) / 1000.0  # Convert to seconds

        # Find N such that total_time(N) is close to total_duration
        N_min = 1
        N_max = 10000  # Arbitrary large number
        N = N_min
        while N_min < N_max:
            N = (N_min + N_max) // 2
            t = total_time(N)
            if abs(t - total_duration) < 0.01:
                break
            if t < total_duration:
                N_min = N + 1
            else:
                N_max = N - 1

        self.total_frames = N

        # Now calculate the actual intervals
        progress_list = [(i / (N - 1)) for i in range(N)]
        intervals = [start_interval_ms + (final_interval_ms - start_interval_ms) * (p ** exponent) for p in progress_list]
        # Adjust the last interval to make the total duration exact
        total_intervals_time = sum(intervals)
        correction = (total_duration * 1000.0 - total_intervals_time) / N
        intervals = [interval + correction for interval in intervals]

        return intervals

    def update_lights(self):
        """Update the highlighted employees during the lottery."""
        if self.frame_count >= self.total_frames:
            self.timer.stop()

            # 清除高亮（保留中獎者）
            for i in range(self.grid_layout.count()):
                widget = self.grid_layout.itemAt(i).widget()
                employee_name = widget.text()
                if employee_name not in self.winner_records[self.current_reward]:
                    widget.setStyleSheet("border: 1px solid black; padding: 5px;")

            # 確定中獎者

            available_indices = [
                i for i in range(len(self.rewards[self.current_reward]))
                if self.rewards[self.current_reward][i] not in self.winner_records[self.current_reward]
            ]
            if not available_indices:
                return
            pick_count = min(self.pick_spinner.value(), len(available_indices))
            self.winner_indices = self.current_indices[:pick_count]

            # 高亮中獎者為紅色
            for idx in self.winner_indices:
                widget = self.grid_layout.itemAt(idx).widget()
                widget.setStyleSheet("background-color: red; border: 2px solid black; padding: 5px;")

            # 更新中獎紀錄（延遲轉換為黃色）
            winners = [self.rewards[self.current_reward][idx] for idx in self.winner_indices]
            self.winner_records[self.current_reward].extend(winners)
            self.update_winner_label()
            
            # 儲存中獎結果到檔案
            print(f">>> New Winner : {winners}, {self.current_reward}")
            self._save_results_to_file(winners)
            self.statusBar().showMessage(f"<<{self.current_reward}>> 中獎者 : {winners} || 得獎名單寫入至[{self.result_file}]")

            # 更新其他視圖與邏輯
            self.update_winner_label()
            self.play_music("resources/winner_sound.mp3")
            self.pull_button.setEnabled(True)
            self.highlighting_winner = True
            
            # 播放中獎音效
            self.play_music("resources/winner_sound.mp3")

            # 啟用 PULL 按鈕
            self.pull_button.setEnabled(True)
            self.highlighting_winner = True  # 標記高亮中獎者

            return

        # 清除先前的高亮（保留當次紅色高亮）
        for i in range(self.grid_layout.count()):
            widget = self.grid_layout.itemAt(i).widget()
            employee_name = widget.text()
            if employee_name not in self.winner_records[self.current_reward]:
                widget.setStyleSheet("border: 1px solid black; padding: 5px;")

        # 更新當前高亮的員工
        available_indices = [
            i for i in range(len(self.rewards[self.current_reward]))
            if self.rewards[self.current_reward][i] not in self.winner_records[self.current_reward]
        ]
        if not available_indices:
            self.timer.stop()
            return

        pick_count = min(self.pick_spinner.value(), len(available_indices))
        if self.mode_combo.currentText() == "隨機歷遍" or self.mode_combo.currentText() == "AI部門":
            # 计算未被抽中的人数
            non_pick_count = len(available_indices) - pick_count

            if pick_count < non_pick_count:
                # 避免连续高亮相同的人
                if hasattr(self, 'last_selected_indices'):
                    candidates = [i for i in available_indices if i not in self.last_selected_indices]
                else:
                    candidates = available_indices

                if not candidates:
                    candidates = available_indices

                self.current_indices = random.sample(candidates, pick_count)

                # 记录当前被选中的索引
                self.last_selected_indices = self.current_indices
                # 更新上次未被选中的索引
                self.last_excluded_indices = [i for i in available_indices if i not in self.current_indices]
            elif pick_count > non_pick_count:
                # 避免连续不高亮相同的人
                exclude_count = non_pick_count

                if hasattr(self, 'last_excluded_indices'):
                    exclusion_candidates = [i for i in available_indices if i not in self.last_excluded_indices]
                else:
                    exclusion_candidates = available_indices

                if not exclusion_candidates:
                    exclusion_candidates = available_indices

                excluded_indices = random.sample(exclusion_candidates, exclude_count)

                self.current_indices = [i for i in available_indices if i not in excluded_indices]

                # 记录当前被选中和未被选中的索引
                self.last_selected_indices = self.current_indices
                self.last_excluded_indices = excluded_indices
            else:
                # 当抽取人数与未抽取人数相同时，允许重复抽取
                self.current_indices = random.sample(available_indices, pick_count)

                # 记录当前被选中和未被选中的索引
                self.last_selected_indices = self.current_indices
                self.last_excluded_indices = [i for i in available_indices if i not in self.current_indices]

            # 高亮当前员工
            for idx in self.current_indices:
                widget = self.grid_layout.itemAt(idx).widget()
                widget.setStyleSheet("background-color: red; border: 2px solid black; padding: 5px;")

            # 播放滚动音效
            self.play_sound_effect(self.rolling_sound)

            # 更新帧计数和计时器间隔
            self.frame_count += 1
            if self.frame_count < len(self.intervals):
                self.timer.setInterval(int(self.intervals[self.frame_count]))
            else:
                self.timer.setInterval(int(self.intervals[-1]))

        else:
            # 循序歷遍模式
            indices = []
            for i in range(pick_count):
                idx = (self.seq_index + i) % len(available_indices)
                indices.append(available_indices[idx])
            self.seq_index = (self.seq_index + pick_count) % len(available_indices)
            self.current_indices = indices

        # 高亮當前員工
        for idx in self.current_indices:
            widget = self.grid_layout.itemAt(idx).widget()
            widget.setStyleSheet("background-color: red; border: 2px solid black; padding: 5px;")

        # 播放滾動音效
        self.play_sound_effect(self.rolling_sound)

        # 更新幀計數和計時器間隔
        self.frame_count += 1
        if self.frame_count < len(self.intervals):
            self.timer.setInterval(int(self.intervals[self.frame_count]))
        else:
            self.timer.setInterval(int(self.intervals[-1]))

    def update_winner_label(self):
        """Update the winner grid with the current reward's winners."""
        self.populate_winner_grid()

    def play_sound_effect(self, sound):
        """Play rolling sound effect."""
        try:
            if self.sound_channel.get_busy():
                self.sound_channel.stop()
            self.sound_channel.play(sound)
        except Exception as e:
            print(f"音效撥放失敗: {e}")

    def play_music(self, file_path):
        """Play winner music."""
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"音樂撥放失敗: {e}")

def check_resources():
    """檢查必要的資源檔案與獎項檔案是否存在。"""
    # 定義必要的資源路徑
    required_files = [
        "resources/rolling_sound.wav",
        "resources/winner_sound.mp3",
        "resources/icon.png"
    ]
    required_folders = ["rewards"]

    # 檢查檔案
    missing_files = [f for f in required_files if not os.path.exists(f)]
    missing_folders = [f for f in required_folders if not os.path.exists(f)]

    # 如果有缺失，返回缺失項目
    if missing_files or missing_folders:
        return missing_files + missing_folders
    return None

def set_global_font(app):
    """設定全域字體為微軟正黑體。"""
    font = app.font()
    font.setFamily("Microsoft JhengHei")
    app.setFont(font)

if __name__ == "__main__":
    print("||||||||||||||||||||||||||||||||||||||||")
    print("||| Welcome to use Rontgen Roulette! |||")
    print("||| Power by Rontgen, DongZhuWorks.  |||")
    print("||||||||||||||||||||||||||||||||||||||||")
    # 檢查資源完整性
    missing_resources = check_resources()
    if missing_resources:
        app = QApplication(sys.argv)
        set_global_font(app)  # 設定全域字體
        QMessageBox.critical(
            None,
            "資源缺失",
            f"以下資源檔案或資料夾缺失，請檢查後再執行程式：\n\n" + "\n".join(missing_resources) + "\n\n(rewards資料夾內需有`獎項.txt`)",
        )
        sys.exit(1)  # 終止程式

    app = QApplication(sys.argv)
    set_global_font(app)  # 設定全域字體
    lottery_app = RouletteApp()
    lottery_app.show()
    sys.exit(app.exec_())
