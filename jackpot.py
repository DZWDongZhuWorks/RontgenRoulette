import sys
import os
import random
import math
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QGridLayout, QWidget, QComboBox, QSpinBox
)
from PySide2.QtGui import QColor
from PySide2.QtCore import Qt, QTimer, QTime
import pygame

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

        # Iteration time (seconds), default random between 5 and 50
        self.duration_label = QLabel("历遍时间(秒):")
        self.duration_spinner = QSpinBox()
        self.duration_spinner.setRange(5, 50)
        self.duration_spinner.setValue(random.randint(5, 50))
        reward_layout.addWidget(self.duration_label)
        reward_layout.addWidget(self.duration_spinner)

        # Starting interval time (seconds), default 0.5
        self.start_interval_label = QLabel("起始间隔(秒):")
        self.start_interval_spinner = QSpinBox()
        self.start_interval_spinner.setRange(1, 5000)
        self.start_interval_spinner.setValue(500)  # Default 500 ms
        reward_layout.addWidget(self.start_interval_label)
        reward_layout.addWidget(self.start_interval_spinner)

        # Final interval time (seconds), default 2
        self.final_interval_label = QLabel("最终间隔(秒):")
        self.final_interval_spinner = QSpinBox()
        self.final_interval_spinner.setRange(1, 5000)
        self.final_interval_spinner.setValue(2000)  # Default 2000 ms
        reward_layout.addWidget(self.final_interval_label)
        reward_layout.addWidget(self.final_interval_spinner)

        main_layout.addLayout(reward_layout)

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

        self.update_reward()

    def update_reward(self):
        """Update current reward and employee pool."""
        self.current_reward = self.reward_combo.currentText()
        self.populate_employee_grid()

        # Clear winner records for this reward
        self.winner_records[self.current_reward] = []
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
            label.setStyleSheet("border: 1px solid black; padding: 5px;")
            self.grid_layout.addWidget(label, row, col)

    def start_lottery(self):
        """Start the lottery drawing."""
        employees = self.rewards[self.current_reward]
        pick_count = self.pick_spinner.value()
        mode = self.mode_combo.currentText()
        total_duration = self.duration_spinner.value()  # Total iteration time in seconds

        # Get starting and final intervals in seconds
        start_interval = self.start_interval_spinner.value() / 1000.0
        final_interval = self.final_interval_spinner.value() / 1000.0

        # Validate pick_count
        if pick_count > len(employees):
            pick_count = len(employees)
            self.pick_spinner.setValue(pick_count)

        # Initialize variables for the lottery
        self.frame_count = 0
        self.total_frames = int(total_duration * 30)  # Assuming 30 frames per second
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
        self.intervals = self.calculate_intervals(total_duration, start_interval, final_interval)

        # Start the timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_lights)
        self.timer.start(int(self.intervals[0] * 1000))  # Start with the first interval

    def calculate_intervals(self, total_duration, start_interval, final_interval):
        """Calculate intervals for the timer to create a slowing down effect."""
        total_frames = int(total_duration * 30)  # Assuming 30 frames per second
        intervals = []
        for i in range(total_frames):
            progress = i / total_frames
            interval = start_interval + (final_interval - start_interval) * (progress ** 2)  # Exponential slowdown
            intervals.append(interval)
        return intervals

    def update_lights(self):
        """Update the highlighted employees during the lottery."""
        if self.frame_count >= len(self.intervals):
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
                self.winner_indices = [self.current_indices[i % len(self.current_indices)] for i in range(self.pick_spinner.value())]

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
            if not hasattr(self, 'seq_index'):
                self.seq_index = 0
            available_indices = [i for i in range(len(self.rewards[self.current_reward])) if self.rewards[self.current_reward][i] not in self.winner_records[self.current_reward]]
            if not available_indices:
                self.timer.stop()
                return
            self.current_indices = [available_indices[(self.seq_index + i) % len(available_indices)] for i in range(self.pick_spinner.value())]
            self.seq_index = (self.seq_index + self.pick_spinner.value()) % len(available_indices)

        # Highlight current employees
        for idx in self.current_indices:
            widget = self.grid_layout.itemAt(idx).widget()
            widget.setStyleSheet("background-color: red; border: 2px solid black; padding: 5px;")

        # Play rolling sound
        self.play_sound_effect(self.rolling_sound)

        # Update frame count and timer interval
        self.frame_count += 1
        if self.frame_count < len(self.intervals):
            self.timer.setInterval(int(self.intervals[self.frame_count] * 1000))

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
