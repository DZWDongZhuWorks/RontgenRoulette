import sys
import os
import random
import math
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QGridLayout, QWidget, QComboBox, QSpinBox, QSizePolicy, QMessageBox,
    QFileDialog, QAction, QDialog, QTextEdit
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
        self.reward_info = {}
        self.current_reward_info = None
        self.current_reward_id = None
        self.load_rewards()
        self.init_ui()
        self.highlighting_winner = False  # 新增布林變數
        self.recursion = 0 # 連抽模式的遞迴次數
        
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
                writer.writerow(["員工姓名", "完整獎項名稱", "獎項ID"])
            self.file_initialized = True

    def _save_results_to_file(self, winners):
        """將中獎結果寫入檔案"""
        if not self.file_initialized:
            self._initialize_result_file()
        # 將中獎者寫入檔案
        with open(self.result_file, "a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file, delimiter=",")
            fullrewardName = self.current_reward_info['fullrewardName']
            rewardID = self.current_reward_info['rewardID']
            for winner in winners:
                writer.writerow([winner, fullrewardName, rewardID])
                
    def load_rewards(self):
        """Load prize lists from txt files in rewards folder with updated format."""
        self.reward_info = {}
        self.reward_ids = []
        error_files = []  # 用於累積不符合條件的檔名
        
        for file in os.listdir(self.rewards_folder):
            if file.endswith(".txt"):
                components = os.path.splitext(file)[0].split('_')
                if len(components) != 2:  # 檢查檔名是否符合格式
                    error_files.append(file)
                    continue
                
                index, show_name = components
                file_path = os.path.join(self.rewards_folder, file)
                
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.read().splitlines()
                except Exception as e:
                    error_files.append(f"{file} (無法讀取: {str(e)})")
                    continue

                if len(lines) < 4:  # 檢查檔案內是否至少包含4行（基本資料+員工名單）
                    error_files.append(file)
                    continue

                try:
                    # 解析獎項基本資料
                    full_name = lines[0].split(",", 1)[1].strip() if ',' in lines[0] else ""
                    pick_num_str = lines[1].split(",", 1)[1].strip() if ',' in lines[1] else "0"
                    rainbow_format = lines[2].split(",", 1)[1].strip() if ',' in lines[2] else ""
                    reward_id = lines[3].split(",", 1)[1].strip() if ',' in lines[3] else ""

                    # 檢查 PickNum 是否為有效整數
                    try:
                        pick_num = int(pick_num_str)
                    except ValueError:
                        error_files.append(f"{file} (PickNum 非有效整數)")
                        continue
                    
                    # 獎項ID不得重複
                    if reward_id in self.reward_info and reward_id != "":
                        error_files.append(f"{file} (RewardID 重複)")
                        continue

                    # 解析員工名單
                    employees = lines[4:]

                    self.reward_ids.append(index)
                    self.reward_info[index] = {
                        'index': index,
                        'fullrewardName': full_name,
                        'ShowrewardName': show_name,
                        'pickNum': pick_num,
                        'RainbowFormat': rainbow_format,
                        'rewardID': reward_id,
                        'employees': employees,
                        'winners': []
                    }
                except Exception as e:
                    error_files.append(f"{file} (解析失敗: {str(e)})")
                    continue

        # 如果有錯誤的檔案，顯示錯誤訊息
        if error_files:
            error_message = (
                "以下獎項清單檔案格式錯誤，未被載入於程式中：\n\n"
                + "\n".join(error_files)
                + "\n\n-------------------------------"
                + "\n`獎項.txt`檔名格式須符合 Index_ShowName.txt，"
                + "檔案內容前四行格式如下：\n"
                + "FullName,全名\nPickNum,數字\nRainbowFormat,參數\nRewardID,參數\n"
                + "其餘行為員工名單。"
            )
            print(error_message)  # 可選擇印到 console 或用 QMessageBox 顯示
            QMessageBox.critical(None, "獎項清單載入失敗", error_message)

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
        # Add items to combo box
        for index in self.reward_ids:
            ShowrewardName = self.reward_info[index]['ShowrewardName']
            self.reward_combo.addItem(ShowrewardName, userData=self.reward_info[index]['rewardID'])
        self.reward_combo.currentIndexChanged.connect(self.update_reward)
        reward_layout.addWidget(self.reward_label)
        reward_layout.addWidget(self.reward_combo)

        # Pick number selection (1-50)
        self.pick_label = QLabel("單抽人數:")
        set_font(self.pick_label, font_size)
        self.pick_spinner = QSpinBox()
        set_font(self.pick_spinner, font_size)
        self.pick_spinner.setRange(1, 50)
        reward_layout.addWidget(self.pick_label)
        reward_layout.addWidget(self.pick_spinner)

        # Mode selection
        self.mode_label = QLabel("抽取模式:")
        set_font(self.mode_label, font_size)
        self.mode_combo = QComboBox()
        set_font(self.mode_combo, font_size)
        # 新增 "AI部門" 選項
        self.mode_combo.addItems(["隨機歷遍", "循序歷遍", "連抽模式"])
        self.mode_combo.currentIndexChanged.connect(self.update_mode)
        reward_layout.addWidget(self.mode_label)
        reward_layout.addWidget(self.mode_combo)
        
        # Color selection
        self.color_label = QLabel("得獎顯色:")
        set_font(self.color_label, font_size)
        self.color_combo = QComboBox()
        set_font(self.color_combo, font_size)

        self.color_combo.addItems(["單色", "彩色"])
        self.color_combo.currentIndexChanged.connect(self.update_color_mode)
        reward_layout.addWidget(self.color_label)
        reward_layout.addWidget(self.color_combo)
        
        # Iteration time range (seconds)
        self.duration_label = QLabel("歷遍範圍(秒):")
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
        self.final_interval_spinner.setRange(2, 5000)
        self.final_interval_spinner.setValue(500)  # Default 2000 ms
        reward_layout.addWidget(self.final_interval_label)
        reward_layout.addWidget(self.final_interval_spinner)

        main_layout.addLayout(reward_layout)

        # Create a menu bar
        menubar = self.menuBar()
        dev_menu = menubar.addMenu('Dev')

        # Add Import action
        import_action = QAction('Import Winning List', self)
        import_action.triggered.connect(self.import_winning_list)
        dev_menu.addAction(import_action)
        
        # Add Import action
        about_me = QAction('About Rontgen Roulette', self)
        about_me.triggered.connect(self.about_me)
        dev_menu.addAction(about_me)

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
        current_index = self.reward_combo.currentIndex()
        current_rewardID = self.reward_combo.itemData(current_index)
        self.current_reward_id = current_rewardID

        # Get the correct index from self.reward_ids
        index = self.reward_ids[current_index]
        current_reward_info = self.reward_info[index]
        self.current_reward_info = current_reward_info
        ShowrewardName = current_reward_info['ShowrewardName']
        fullrewardName = current_reward_info['fullrewardName']
        pickNum = current_reward_info['pickNum']
        employees = current_reward_info['employees']

        # Update prize_label to display ShowrewardName
        if self.mode_combo.currentText() == "連抽模式":
            self.prize_label.setText(f"本次獎項：{ShowrewardName}\n紅色:五獎*2 | 橙色:四獎*2 | 黃色:三獎*2 | 綠色:二獎*2 | 藍色:一獎*1")
        else:
            self.prize_label.setText(f"本次獎項：{ShowrewardName}")
        
        # 清空 winner_indices，避免舊獎項索引干擾新獎項
        self.winner_indices = []

        # Initialize winner records for this reward if not already
        if 'winners' not in current_reward_info:
            current_reward_info['winners'] = []
        self.populate_employee_grid()
        self.update_winner_label()

    def update_mode(self):
        if self.mode_combo.currentText() == "連抽模式":
            self.pick_label.setText("連抽人數:")
            self.duration_lower_spinner.setValue(1)
            self.duration_upper_spinner.setValue(1)
            self.start_interval_spinner.setValue(1)
            self.final_interval_spinner.setValue(20)
            ShowrewardName = self.current_reward_info['ShowrewardName']
            self.prize_label.setText(f"本次獎項：{ShowrewardName}\n紅色:五獎*2 | 橙色:四獎*2 | 黃色:三獎*2 | 綠色:二獎*2 | 藍色:一獎*1")
        else:
            self.pick_label.setText("單抽人數:")
            self.duration_lower_spinner.setValue(3)
            self.duration_upper_spinner.setValue(10)
            self.start_interval_spinner.setValue(100)
            self.final_interval_spinner.setValue(500)
            ShowrewardName = self.current_reward_info['ShowrewardName']
            self.prize_label.setText(f"本次獎項：{ShowrewardName}")  

    def update_color_mode(self):
        self.populate_winner_grid()

    def populate_winner_grid(self):
        """Populate the winner grid with the current reward's winners."""
        # Clear existing grid
        for i in reversed(range(self.winner_grid_layout.count())):
            widget = self.winner_grid_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Get the winners for the current reward
        winners = self.current_reward_info['winners']
        num_winners = len(winners)

        # If no winners, do nothing
        if num_winners == 0:
            return

        # Define fixed grid size
        grid_width = 220  # Fixed width for each grid
        grid_height = 80  # Fixed height for each grid

        cols = 8  # Fixed number of columns
        rows = (num_winners + cols - 1) // cols  # Calculate number of rows

        # Get the current mode
        mode = self.color_combo.currentText()
        rainbow_format = self.current_reward_info['RainbowFormat']
        # Define rainbow colors list
        rainbow_colors = [
            "#FF0000",  # Red
            "#FFA500",  # Orange
            "#FFFF00",  # Yellow
            "#008000",  # Green
            "#2F67D7",  # Blue
            "#8E3AC6",  # Indigo
            "#EE82EE",  # Violet
        ]

        # Function to parse rainbow_format
        def parse_rainbow_format(rainbow_format):
            counts = []
            for c in rainbow_format:
                if '1' <= c <= '9':
                    counts.append(int(c))
                elif 'A' <= c <= 'Z':
                    counts.append(ord(c) - ord('A') + 10)
            return counts

        if mode == "彩色":
            if rainbow_format != "":
                counts_list = parse_rainbow_format(rainbow_format)
                color_index = 0
                if counts_list:
                    count_remaining = counts_list.pop(0)
                else:
                    count_remaining = 2  # Default to 2 if counts_list is empty
                default_remaining = 2
            else:
                pass  # Will use default rule in the loop

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
            if mode == "彩色":
                if rainbow_format != "":
                    # Use rainbow_format to determine color change
                    background_color = rainbow_colors[color_index % len(rainbow_colors)]
                    label.setStyleSheet(f"background-color: {background_color}; border: 3px solid black; padding: 2px;")
                    # Decrement count_remaining
                    count_remaining -= 1
                    if count_remaining == 0:
                        color_index += 1
                        if counts_list:
                            count_remaining = counts_list.pop(0)
                        else:
                            # counts_list is exhausted, use default rule
                            count_remaining = default_remaining
                else:
                    # Use default rule, change color every two people
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

        employees = self.current_reward_info['employees']
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
            if employee in self.current_reward_info['winners']:
                label.setStyleSheet("background-color: yellow; border: 2px solid black; padding: 5px;")
            else:
                label.setStyleSheet("border: 1px solid black; padding: 5px;")

            self.grid_layout.addWidget(label, row, col)

    def start_lottery(self):
        self.pick_count_temp = self.pick_spinner.value()
        
        if self.mode_combo.currentText() == "連抽模式":
            self.pick_spinner.setValue(1)
            self.recursion = self.pick_count_temp -1 # 因為還沒進recursion前已經先跑一次
            self.start_lottery_unit()                
        else:
            self.start_lottery_unit()

    def start_lottery_unit(self):
        """Start the lottery drawing."""
        # 如果有高亮的中獎者，先將其轉為黃色
        if self.highlighting_winner:
            self.highlight_winners_to_yellow()

        # 取得單抽人數和已中獎人數
        pick_count = self.pick_spinner.value()
        pickNum = self.current_reward_info['pickNum']
        total_winners = len(self.current_reward_info['winners'])
        potential_total_winners = total_winners + pick_count

        # Check if next draw will exceed pickNum
        if potential_total_winners > pickNum:
            # Show dialog to confirm
            reply = QMessageBox.question(self, '警告',
                                         f"此次抽獎人數將使得總中獎人數 ({potential_total_winners}) 超過抽取上限 {pickNum}，是否繼續？",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return


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
        employees = self.current_reward_info['employees']
        pick_count = self.pick_spinner.value()
        mode = self.mode_combo.currentText()
        total_duration = iteration_time  # Use the iteration time from the wheel

        # Get starting and final intervals in milliseconds
        start_interval_ms = self.start_interval_spinner.value()
        final_interval_ms = self.final_interval_spinner.value()

        # Validate pick_count
        # available_employees = [e for e in employees if e not in self.current_reward_info['winners']]
        # remaining_slots = self.current_reward_info['pickNum'] - len(self.current_reward_info['winners'])
        # pick_count = min(pick_count, len(available_employees), remaining_slots)
        # self.pick_spinner.setValue(pick_count)

        # if pick_count <= 0:
        #     QMessageBox.information(self, '訊息', '沒有可用的員工進行抽獎。')
        #     self.pull_button.setEnabled(True)
        #     return

        # Initialize variables for the lottery
        self.frame_count = 0
        self.total_frames = 0
        self.current_indices = []
        self.winner_indices = []  # 清空舊的中獎索引
        self.available_indices = [i for i, e in enumerate(employees) if e not in self.current_reward_info['winners']]

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

        # Estimate the number of frames based on average interval
        average_interval_ms = (start_interval_ms + final_interval_ms) / 2.0
        N = max(2, int((total_duration * 1000.0) / average_interval_ms))

        # Generate progress list for the deceleration curve
        progress_list = [(i / (N - 1)) for i in range(N)]
        intervals = [start_interval_ms + (final_interval_ms - start_interval_ms) * (p ** exponent) for p in progress_list]

        # Calculate total intervals time
        total_intervals_time = sum(intervals)

        # Compute scaling factor to match the total_duration
        scale = (total_duration * 1000.0) / total_intervals_time

        # Scale intervals to match the total duration
        intervals = [interval * scale for interval in intervals]

        self.total_frames = N

        return intervals
    
    def update_lights(self):
        """Update the highlighted employees during the lottery."""
        # Initialize elapsed time if not already
        if not hasattr(self, 'elapsed_time'):
            self.elapsed_time = 0

        # Update elapsed time
        self.elapsed_time += self.timer.interval()

        if self.elapsed_time >= self.total_duration * 1000.0:
            self.timer.stop()
            del self.elapsed_time  # Reset for next time

            # 清除高亮（保留中獎者）
            for i in range(self.grid_layout.count()):
                widget = self.grid_layout.itemAt(i).widget()
                employee_name = widget.text()
                if employee_name not in self.current_reward_info['winners']:
                    widget.setStyleSheet("border: 1px solid black; padding: 5px;")

            # 確定中獎者

            available_indices = [
                i for i in range(len(self.current_reward_info['employees']))
                if self.current_reward_info['employees'][i] not in self.current_reward_info['winners']
            ]
            if not available_indices:
                return
            pick_count = min(self.pick_spinner.value(), len(available_indices))
            # remaining_slots = self.current_reward_info['pickNum'] - len(self.current_reward_info['winners'])
            # pick_count = min(pick_count, remaining_slots)
            self.winner_indices = self.current_indices[:pick_count]

            # 高亮中獎者為紅色
            for idx in self.winner_indices:
                widget = self.grid_layout.itemAt(idx).widget()
                widget.setStyleSheet("background-color: red; border: 2px solid black; padding: 5px;")

            # 更新中獎紀錄（延遲轉換為黃色）
            employees = self.current_reward_info['employees']
            winners = [employees[idx] for idx in self.winner_indices]
            self.current_reward_info['winners'].extend(winners)
            self.update_winner_label()
            
            # 儲存中獎結果到檔案
            print(f">>> New Winner : {winners}, {self.current_reward_info['fullrewardName']}")
            self._save_results_to_file(winners)
            self.statusBar().showMessage(f"<<{self.current_reward_info['ShowrewardName']}>> 中獎者 : {winners} || 得獎名單寫入至[{self.result_file}]")

            # 更新其他視圖與邏輯
            self.update_winner_label()
            
            self.pull_button.setEnabled(True)
            self.highlighting_winner = True
            
            # 啟用 PULL 按鈕
            self.pull_button.setEnabled(True)
            self.highlighting_winner = True  # 標記高亮中獎者
            if self.recursion > 0 :
                self.recursion -= 1
                self.start_lottery_unit()
            else:
                self.play_music("resources/winner_sound.mp3")
                self.pick_spinner.setValue(self.pick_count_temp)
                
            return

        # 清除先前的高亮（保留當次紅色高亮）
        for i in range(self.grid_layout.count()):
            widget = self.grid_layout.itemAt(i).widget()
            employee_name = widget.text()
            if employee_name not in self.current_reward_info['winners']:
                widget.setStyleSheet("border: 1px solid black; padding: 5px;")

        # 更新當前高亮的員工
        available_indices = [
            i for i in range(len(self.current_reward_info['employees']))
            if self.current_reward_info['employees'][i] not in self.current_reward_info['winners']
        ]
        if not available_indices:
            self.timer.stop()
            return

        pick_count = min(self.pick_spinner.value(), len(available_indices))
        # remaining_slots = self.current_reward_info['pickNum'] - len(self.current_reward_info['winners'])
        # pick_count = min(pick_count, remaining_slots)
        # if pick_count <= 0:
        #     self.timer.stop()
        #     return

        if self.mode_combo.currentText() == "隨機歷遍" or self.mode_combo.currentText() == "連抽模式":
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
            next_interval = self.intervals[self.frame_count]
            self.timer.setInterval(max(int(next_interval), 1))  # 确保至少为1毫秒
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

    def import_winning_list(self):
        """Import winning list csv and restore the draw state."""
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self, "Import Winning List", "",
                                                "CSV Files (*.csv);;All Files (*)", options=options)
        if fileName:
            try:
                with open(fileName, 'r', encoding='utf-8-sig') as file:
                    reader = csv.reader(file, delimiter=",")
                    headers = next(reader)
                    for row in reader:
                        if len(row) < 3:
                            continue
                        winner_name, fullrewardName, rewardID = row[:3]
                        # 在 self.reward_info 中查找匹配的 rewardID
                        reward_found = False
                        for reward_info in self.reward_info.values():
                            if reward_info['rewardID'] == rewardID:
                                if winner_name not in reward_info['winners']:
                                    reward_info['winners'].append(winner_name)
                                reward_found = True
                                break
                        if not reward_found:
                            print(f"Reward ID {rewardID} not found in current rewards.")
                QMessageBox.information(self, "導入成功", "中獎名單已匯入，抽獎狀態已恢復")
                self.update_reward()
            except Exception as e:
                QMessageBox.critical(self, "導入錯誤", f"導入時發生錯誤: {e}")

    def about_me(self):
        """Show dialog about Rontgen Roulette."""
        message = """
        Rontgen Roulette版本 : v5
        最終編譯時間 : 20241205
        
        有關Rontgen Roulette程式中隨機的部分是由什麼函數執行的?
        - python的`random.sample`函數
        
        `random.sample` 是如何運作的？
        - `random.sample(population, k)` 方法從指定的列表（`population`）中隨機選取 `k` 個不重複的元素。
        - 該方法的隨機數生成基於 Mersenne Twister 演算法，這是一種高效能且品質極高的偽隨機數生成器，經廣泛測試被證明具有強大的隨機性。

        如何解釋「隨機性」的公平性？
        - 均勻分佈：每位參與者的選取概率是均勻的，無任何偏向。
        - 獨立事件：每次抽獎的結果都是獨立的，不受上一輪結果的影響。
        - 高效能測試：Mersenne Twister 演算法在多種測試（如 Diehard 測試套件）中證明其隨機性足夠應用於絕大多數非密碼學用途。Mersenne Twister（梅森旋轉演算法）是一個由松本眞和西村拓士於 1997 年開發的偽隨機數生成算法，基於有限二進制欄位上的矩陣線性遞歸。其名稱源自於其周期長度取自梅森質數的特性。

        使用者信心保障
        - 來源可信：Python 是一個廣受社群支持並經過實際驗證的開發環境，`random.sample` 作為其核心函數之一，具有極高的可信度。
        - 透明邏輯：程式的隨機數邏輯公開在程式碼中，使用者可以輕鬆檢視，確認無任何刻意設置的不公平因素。

        透過這些設計，Rontgen Roulette 能夠提供公正、隨機的抽獎體驗，讓參與者感受到真實的隨機性與公平性。如果您仍有疑問，歡迎聯繫開發者進一步了解實作邏輯！

        免責聲明
        使用該程式即視同同意該免責聲明。
        本程式的隨機抽獎結果是基於電腦隨機數生成方法，旨在提供一個公平且無偏的抽獎過程。然而，由於偽隨機數生成的特性，無法保證抽獎結果的完全不可預測性。本程式僅供娛樂用途，開發者不對使用本程式進行的任何活動結果負責。程式中產生任何技術問題與使用糾紛一概與開發者無關。使用者應自行承擔使用本程式所帶來的所有風險和後果。

        聯絡我們
        如有任何問題，請聯繫：
        - 開發者：Rontgen, DongZhuWorks.
        - Email: dongzhuworks@gmail.com
        - 該程式碼的撰寫有 GPT-4 的參與

        """

        # Create a dialog window
        dialog = QDialog(self)
        dialog.setWindowTitle("About Rontgen Roulette")

        # Set up the layout
        layout = QVBoxLayout()

        # Use QTextEdit for scrollable text display
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(message)
        text_edit.setStyleSheet("font-size: 14pt;")

        # Add the text_edit to the layout
        layout.addWidget(text_edit)

        # Set the dialog layout
        dialog.setLayout(layout)

        # Resize the dialog to a reasonable size
        dialog.resize(800, 600)

        # Display the dialog
        dialog.exec_()

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
    print("|||||||||||||||||||||||||||||||||||||||||||")
    print("||| Welcome to use Rontgen Roulette v5! |||")
    print("|||   Power by Rontgen, DongZhuWorks.   |||")
    print("|||||||||||||||||||||||||||||||||||||||||||")
    # 檢查資源完整性
    missing_resources = check_resources()
    if missing_resources:
        app = QApplication(sys.argv)
        set_global_font(app)  # 設定全域字體
        QMessageBox.critical(
            None,
            "資源缺失",
            f"以下資源檔案或資料夾缺失，請檢查後再執行程式：\n\n" + "\n".join(missing_resources) 
            + "\n\n(rewards資料夾內需有`獎項.txt`)"
            + "\n`獎項.txt`檔名格式須符合 Index_ShowName.txt，"
            + "檔案內容前四行格式如下：\n"
            + "FullName,全名\nPickNum,數字\nRainbowFormat,參數\nRewardID,參數\n"
            + "其餘行為員工名單。"
        )
        sys.exit(1)  # 終止程式

    app = QApplication(sys.argv)
    set_global_font(app)  # 設定全域字體
    lottery_app = RouletteApp()
    lottery_app.show()
    sys.exit(app.exec_())
