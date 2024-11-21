import sys
import os
import random
import math
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QGridLayout, QWidget, QComboBox, QSpinBox
)
from PySide2.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PySide2.QtCore import Qt, QTimer, QTime, Signal
import pygame

class WheelWidget(QWidget):
    iteration_time_decided = Signal(float)  # Signal to emit the iteration time when animation finishes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rotation_angle = 0.0
        self.is_animating = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.animation_duration = 5000  # Total animation time in milliseconds
        self.elapsed_time = 0
        self.start_speed = random.uniform(720, 1080)  # Starting speed in degrees per second (2 to 3 rotations per second)
        self.current_speed = self.start_speed
        self.rotation_angles = []
        self.current_frame = 0
        self.total_frames = 0

        # Deceleration exponent
        self.exponent = 2.0

        # For mapping angle to iteration time
        self.lower_limit = 5.0  # Default lower limit in seconds
        self.upper_limit = 50.0  # Default upper limit in seconds

        # Set minimum size
        self.setMinimumSize(300, 300)

    def start_animation(self):
        self.is_animating = True
        self.elapsed_time = 0
        self.current_frame = 0
        self.start_speed = random.uniform(720, 1080)  # Random starting speed
        self.current_speed = self.start_speed
        self.rotation_angle = 0.0

        # Prepare the list of rotation angles
        frame_interval = 16  # milliseconds (approx 60 FPS)
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
            self.update()
            return

        delta_angle = self.rotation_angles[self.current_frame]
        self.rotation_angle += delta_angle
        self.current_frame += 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw wheel background
        radius = min(rect.width(), rect.height()) / 2 - 10
        center = rect.center()

        painter.setPen(QPen(Qt.black, 2))
        painter.setBrush(QBrush(Qt.white))
        painter.drawEllipse(center, radius, radius)

        # Draw sectors with time labels
        num_sectors = 12
        for i in range(num_sectors):
            angle = i * 360 / num_sectors
            proportion = i / num_sectors
            sector_time = self.lower_limit + (self.upper_limit - self.lower_limit) * proportion
            painter.save()
            painter.translate(center)
            painter.rotate(angle + self.rotation_angle)
            painter.setPen(QPen(Qt.black, 1))
            painter.drawLine(0, -radius, 0, -radius + 20)

            # Draw time text
            painter.translate(0, -radius + 40)
            painter.rotate(-angle - self.rotation_angle)
            painter.setFont(QFont("Arial", 10))
            painter.drawText(-20, 5, f"{sector_time:.1f}s")
            painter.restore()

        # Draw pointer
        painter.setPen(QPen(Qt.red, 4))
        painter.drawLine(center.x(), center.y(), center.x(), center.y() - radius)

        # Add title text
        painter.setFont(QFont("Arial", 14))
        painter.setPen(Qt.black)
        painter.drawText(rect, Qt.AlignBottom | Qt.AlignHCenter, "歷遍時間轉盤")

    def set_limits(self, lower, upper):
        self.lower_limit = lower
        self.upper_limit = upper


class LotteryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("乐透抽奖程序")
        self.setGeometry(100, 100, 800, 600)

        # Initialize variables
        self.rewards_folder = "rewards"
        self.rewards = {}
        self.current_reward = None
        self.winner_records = {}
        self.load_rewards()
        self.init_ui()

        # Initialize pygame for sound effects
        pygame.mixer.init()
        self.rolling_sound = pygame.mixer.Sound("resources/rolling_sound.wav")
        self.rolling_sound.set_volume(0.5)
        self.sound_channel = pygame.mixer.Channel(0)

    def load_rewards(self):
        """Load prize lists from txt files in rewards folder."""
        for file in os.listdir(self.rewards_folder):
            if file.endswith(".txt"):
                prize_name = os.path.splitext(file)[0]
                with open(os.path.join(self.rewards_folder, file), "r", encoding="utf-8") as f:
                    self.rewards[prize_name] = f.read().splitlines()

    def init_ui(self):
        """Initialize UI components."""
        main_layout = QVBoxLayout()

        # Reward selection layout
        reward_layout = QHBoxLayout()
        self.reward_label = QLabel("当前奖项:")
        self.reward_combo = QComboBox()
        self.reward_combo.addItems(self.rewards.keys())
        self.reward_combo.currentIndexChanged.connect(self.update_reward)
        reward_layout.addWidget(self.reward_label)
        reward_layout.addWidget(self.reward_combo)

        # Pick number selection (1-5)
        self.pick_label = QLabel("抽几人:")
        self.pick_spinner = QSpinBox()
        self.pick_spinner.setRange(1, 5)
        reward_layout.addWidget(self.pick_label)
        reward_layout.addWidget(self.pick_spinner)

        # Mode selection
        self.mode_label = QLabel("模式:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["循序历遍", "随机跳动"])
        reward_layout.addWidget(self.mode_label)
        reward_layout.addWidget(self.mode_combo)

        # Iteration time range (seconds)
        self.duration_label = QLabel("历遍时间范围(秒):")
        self.duration_lower_spinner = QSpinBox()
        self.duration_lower_spinner.setRange(5, 50)
        self.duration_lower_spinner.setValue(5)
        self.duration_upper_spinner = QSpinBox()
        self.duration_upper_spinner.setRange(10, 500)
        self.duration_upper_spinner.setValue(10)
        reward_layout.addWidget(self.duration_label)
        reward_layout.addWidget(self.duration_lower_spinner)
        reward_layout.addWidget(QLabel("至"))
        reward_layout.addWidget(self.duration_upper_spinner)

        # Starting interval time (milliseconds), default 500ms
        self.start_interval_label = QLabel("起始间隔(ms):")
        self.start_interval_spinner = QSpinBox()
        self.start_interval_spinner.setRange(100, 5000)
        self.start_interval_spinner.setValue(100)  # Default 500 ms
        reward_layout.addWidget(self.start_interval_label)
        reward_layout.addWidget(self.start_interval_spinner)

        # Final interval time (milliseconds), default 2000ms
        self.final_interval_label = QLabel("最终间隔(ms):")
        self.final_interval_spinner = QSpinBox()
        self.final_interval_spinner.setRange(100, 5000)
        self.final_interval_spinner.setValue(2000)  # Default 2000 ms
        reward_layout.addWidget(self.final_interval_label)
        reward_layout.addWidget(self.final_interval_spinner)

        main_layout.addLayout(reward_layout)

        # Wheel widget
        self.wheel_widget = WheelWidget()
        main_layout.addWidget(self.wheel_widget)
        # 添加历遍时间显示标签
        self.iteration_time_label = QLabel("本次历遍时间: 0.0 秒")
        self.iteration_time_label.setAlignment(Qt.AlignCenter)
        self.iteration_time_label.setFont(QFont("Arial", 16))
        main_layout.addWidget(self.iteration_time_label)
        # PULL button
        self.pull_button = QPushButton("PULL!")
        self.pull_button.clicked.connect(self.start_lottery)
        main_layout.addWidget(self.pull_button)

        # Employee grid
        self.grid_layout = QGridLayout()
        self.grid_widget = QWidget()
        self.grid_widget.setLayout(self.grid_layout)
        main_layout.addWidget(self.grid_widget)

        # Winner list
        self.winner_label = QLabel("已中奖: ")
        main_layout.addWidget(self.winner_label)

        # Set main layout
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.wheel_widget.iteration_time_decided.connect(self.wheel_animation_finished)

        self.update_reward()

    def update_reward(self):
        """Update current reward and employee pool."""
        self.current_reward = self.reward_combo.currentText()
        # Initialize winner records for this reward if not already
        if self.current_reward not in self.winner_records:
            self.winner_records[self.current_reward] = []
        self.populate_employee_grid()
        self.update_winner_label()

    def populate_employee_grid(self):
        """Populate the employee grid based on the current reward."""
        # Clear existing grid
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        employees = self.rewards[self.current_reward]
        num_employees = len(employees)
        cols = min(10, num_employees)  # Up to 10 columns
        rows = (num_employees + cols - 1) // cols

        # Adjust window size based on number of employees
        self.setFixedSize(min(1000, cols * 100), min(800, rows * 100 + 200))

        for index, employee in enumerate(employees):
            row = index // cols
            col = index % cols
            label = QLabel(employee)
            label.setAlignment(Qt.AlignCenter)
            if employee in self.winner_records[self.current_reward]:
                label.setStyleSheet("background-color: yellow; border: 2px solid black; padding: 5px;")
            else:
                label.setStyleSheet("border: 1px solid black; padding: 5px;")
            self.grid_layout.addWidget(label, row, col)

    def start_lottery(self):
        """Start the lottery drawing."""
        # Disable PULL button
        self.pull_button.setEnabled(False)
        # Start wheel animation
        lower_limit = self.duration_lower_spinner.value()
        upper_limit = self.duration_upper_spinner.value()
        if lower_limit > upper_limit:
            lower_limit, upper_limit = upper_limit, lower_limit
        self.wheel_widget.set_limits(lower_limit, upper_limit)
        self.wheel_widget.start_animation()

    def wheel_animation_finished(self, iteration_time):
        """Slot called when the wheel animation finishes."""
        self.total_duration = iteration_time
        self.statusBar().showMessage(f"本次历遍时间: {iteration_time:.1f} 秒")
        self.iteration_time_label.setText(f"本次历遍时间: {iteration_time:.1f} 秒")

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
        self.winner_indices = []
        self.available_indices = [i for i in range(len(employees)) if employees[i] not in self.winner_records[self.current_reward]]

        # In random jumping mode, pre-select winners
        if mode == "随机跳动":
            if pick_count > len(self.available_indices):
                pick_count = len(self.available_indices)
                self.pick_spinner.setValue(pick_count)
            self.winner_indices = random.sample(self.available_indices, pick_count)

        # Calculate intervals
        self.intervals = self.calculate_intervals(total_duration, start_interval_ms, final_interval_ms)

        # For sequential iteration mode, start from a random position
        if mode == "循序历遍":
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

            # Clear highlights except for winners
            for i in range(self.grid_layout.count()):
                widget = self.grid_layout.itemAt(i).widget()
                employee_name = widget.text()
                if employee_name not in self.winner_records[self.current_reward]:
                    widget.setStyleSheet("border: 1px solid black; padding: 5px;")

            # In sequential iteration mode, select the final highlighted employees as winners
            if self.mode_combo.currentText() == "循序历遍":
                # Ensure no duplicate winners
                available_indices = [i for i in range(len(self.rewards[self.current_reward])) if self.rewards[self.current_reward][i] not in self.winner_records[self.current_reward]]
                if not available_indices:
                    return
                pick_count = min(self.pick_spinner.value(), len(available_indices))
                self.winner_indices = self.current_indices[:pick_count]

            # Highlight winners
            for idx in self.winner_indices:
                widget = self.grid_layout.itemAt(idx).widget()
                widget.setStyleSheet("background-color: yellow; border: 2px solid black; padding: 5px;")

            # Update winner records
            winners = [self.rewards[self.current_reward][idx] for idx in self.winner_indices]
            self.winner_records[self.current_reward].extend(winners)
            self.update_winner_label()

            # Play winner sound
            self.play_music("resources/winner_sound.mp3")

            # Re-enable PULL button
            self.pull_button.setEnabled(True)
            return

        # Clear previous highlights except for winners
        for i in range(self.grid_layout.count()):
            widget = self.grid_layout.itemAt(i).widget()
            employee_name = widget.text()
            if employee_name not in self.winner_records[self.current_reward]:
                widget.setStyleSheet("border: 1px solid black; padding: 5px;")

        # Update current indices
        if self.mode_combo.currentText() == "随机跳动":
            self.current_indices = random.sample(range(len(self.rewards[self.current_reward])), self.pick_spinner.value())
        else:
            # Sequential iteration
            available_indices = [i for i in range(len(self.rewards[self.current_reward])) if self.rewards[self.current_reward][i] not in self.winner_records[self.current_reward]]
            if not available_indices:
                self.timer.stop()
                return
            pick_count = min(self.pick_spinner.value(), len(available_indices))
            indices = []
            for i in range(pick_count):
                idx = (self.seq_index + i) % len(available_indices)
                indices.append(available_indices[idx])
            self.seq_index = (self.seq_index + pick_count) % len(available_indices)
            self.current_indices = indices

        # Highlight current employees
        for idx in self.current_indices:
            widget = self.grid_layout.itemAt(idx).widget()
            widget.setStyleSheet("background-color: red; border: 2px solid black; padding: 5px;")

        # Play rolling sound
        self.play_sound_effect(self.rolling_sound)

        # Update frame count and timer interval
        self.frame_count += 1
        if self.frame_count < len(self.intervals):
            self.timer.setInterval(int(self.intervals[self.frame_count]))
        else:
            self.timer.setInterval(int(self.intervals[-1]))

    def update_winner_label(self):
        """Update the winner list label."""
        winners = self.winner_records.get(self.current_reward, [])
        if winners:
            self.winner_label.setText(f"已中奖: {', '.join(winners)}")
        else:
            self.winner_label.setText("已中奖: ")

    def play_sound_effect(self, sound):
        """Play rolling sound effect."""
        try:
            if self.sound_channel.get_busy():
                self.sound_channel.stop()
            self.sound_channel.play(sound)
        except Exception as e:
            print(f"音效播放失败: {e}")

    def play_music(self, file_path):
        """Play winner music."""
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"音乐播放失败: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    lottery_app = LotteryApp()
    lottery_app.show()
    sys.exit(app.exec_())
