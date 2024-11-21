# main.py

import sys
import os
import time
import random
import math
from PySide2.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QComboBox, QSpinBox, QMessageBox
)
from PySide2.QtCore import QThread, Signal
from PySide2.QtGui import QPixmap, QPainter, QColor, QFont
import pygame


class LotteryThread(QThread):
    update_highlight = Signal(int)
    draw_finished = Signal(list)  # 修改為傳遞多個得獎者

    def __init__(self, employees, traverse_type, traverse_time, start_interval, end_interval, excluded_indices, draw_count):
        super().__init__()
        self.employees = employees
        self.traverse_type = traverse_type
        self.traverse_time = traverse_time
        self.start_interval = start_interval
        self.end_interval = end_interval
        self.excluded_indices = excluded_indices
        self.draw_count = draw_count

    def run(self):
        pygame.mixer.init()
        rolling_sound = pygame.mixer.Sound('resources/rolling_sound.mp3')
        winner_sound = pygame.mixer.Sound('resources/winner_sound.mp3')

        start_time = time.time()
        current_interval = self.start_interval
        elapsed_time = 0

        highlighted = None
        total_employees = len(self.employees)
        indices = [i for i in range(total_employees) if i not in self.excluded_indices]

        if not indices:
            self.draw_finished.emit([])
            return

        selected_winners = []

        # 隨機起始位置
        if self.traverse_type == '循序歷遍':
            idx = random.choice(indices)
        else:
            idx = None

        while elapsed_time < self.traverse_time:
            rolling_sound.play()

            if self.traverse_type == '循序歷遍':
                idx = (idx + 1) % total_employees
                while idx in self.excluded_indices:
                    idx = (idx + 1) % total_employees
            else:
                idx = random.choice(indices)

            highlighted = idx
            self.update_highlight.emit(highlighted)

            time.sleep(current_interval)
            elapsed_time = time.time() - start_time
            current_interval = min(self.end_interval, current_interval * 1.1)

        # 隨機選擇指定數量的得獎者
        winners = random.sample(indices, min(self.draw_count, len(indices)))
        winner_sound.play()
        self.draw_finished.emit([self.employees[i] for i in winners])


class EmployeePool(QWidget):
    def __init__(self, employees):
        super().__init__()
        self.employees = employees
        self.winners = []
        self.highlighted = None
        self.init_ui()

    def init_ui(self):
        self.setMinimumSize(800, 600)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(255, 255, 255))

        total = len(self.employees)
        cols = math.ceil(math.sqrt(total))
        rows = math.ceil(total / cols)
        cell_width = self.width() / cols
        cell_height = self.height() / rows

        font = QFont('Arial', int(min(cell_width, cell_height) / 5))
        painter.setFont(font)

        for idx, employee in enumerate(self.employees):
            col = idx % cols
            row = idx // cols
            x = col * cell_width
            y = row * cell_height
            rect = (x, y, cell_width, cell_height)

            if idx in self.winners:
                painter.setBrush(QColor(255, 215, 0))  # 金色
            elif idx == self.highlighted:
                painter.setBrush(QColor(135, 206, 250))  # 淺藍色
            else:
                painter.setBrush(QColor(200, 200, 200))

            painter.drawRect(x, y, cell_width, cell_height)
            painter.drawText(x, y, cell_width, cell_height, 1 | 4, employee)


class LotteryApp(QWidget):
    def __init__(self, rewards):
        super().__init__()
        self.rewards = rewards
        self.current_prize = None
        self.employees = []
        self.winners = []
        self.excluded_indices = []
        self.lottery_thread = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('抽獎程式')

        layout = QVBoxLayout()

        # 獎項切換選單
        self.prize_combo = QComboBox()
        self.prize_combo.addItems(self.rewards.keys())
        self.prize_combo.currentTextChanged.connect(self.on_prize_changed)
        layout.addWidget(QLabel("選擇獎項："))
        layout.addWidget(self.prize_combo)

        # 用戶參數設定
        params_layout = QVBoxLayout()

        # 單次抽取人數
        self.draw_count = QSpinBox()
        self.draw_count.setRange(1, 5)
        self.draw_count.setValue(1)
        params_layout.addWidget(QLabel("單次抽取人數："))
        params_layout.addWidget(self.draw_count)

        # 歷遍類型
        self.traverse_type = QComboBox()
        self.traverse_type.addItems(["循序歷遍", "隨機跳動"])
        params_layout.addWidget(QLabel("歷遍類型："))
        params_layout.addWidget(self.traverse_type)

        # 歷遍時間上下限
        time_layout = QHBoxLayout()
        self.traverse_time_min = QSpinBox()
        self.traverse_time_min.setRange(5, 500)
        self.traverse_time_min.setValue(5)
        time_layout.addWidget(QLabel("歷遍時間下限（秒）："))
        time_layout.addWidget(self.traverse_time_min)

        self.traverse_time_max = QSpinBox()
        self.traverse_time_max.setRange(5, 500)
        self.traverse_time_max.setValue(50)
        time_layout.addWidget(QLabel("歷遍時間上限（秒）："))
        time_layout.addWidget(self.traverse_time_max)
        params_layout.addLayout(time_layout)

        # 起始與最終間隔
        interval_layout = QHBoxLayout()
        self.start_interval = QSpinBox()
        self.start_interval.setRange(1, 1000)
        self.start_interval.setValue(500)
        interval_layout.addWidget(QLabel("起始間隔（毫秒）："))
        interval_layout.addWidget(self.start_interval)

        self.end_interval = QSpinBox()
        self.end_interval.setRange(1, 5000)
        self.end_interval.setValue(2000)
        interval_layout.addWidget(QLabel("最終間隔（毫秒）："))
        interval_layout.addWidget(self.end_interval)
        params_layout.addLayout(interval_layout)

        layout.addLayout(params_layout)

        # 歷遍時間顯示
        self.selected_traverse_time_label = QLabel("本次歷遍時間：未選擇")
        layout.addWidget(self.selected_traverse_time_label)

        # 員工池
        self.employee_pool = EmployeePool(self.employees)
        layout.addWidget(self.employee_pool)

        # PULL 按鈕
        self.pull_button = QPushButton("PULL")
        self.pull_button.clicked.connect(self.start_draw)
        layout.addWidget(self.pull_button)

        # 已中獎名單
        self.winner_list = QListWidget()
        layout.addWidget(QLabel("已中獎名單："))
        layout.addWidget(self.winner_list)

        self.setLayout(layout)
        self.on_prize_changed(self.prize_combo.currentText())

    def on_prize_changed(self, prize):
        self.current_prize = prize
        self.employees = self.rewards[prize]
        self.winners = []
        self.excluded_indices = []
        self.employee_pool.employees = self.employees
        self.employee_pool.winners = []
        self.employee_pool.highlighted = None
        self.employee_pool.update()
        self.winner_list.clear()

    def start_draw(self):
        if self.lottery_thread and self.lottery_thread.isRunning():
            QMessageBox.warning(self, "警告", "抽獎進行中，請稍後")
            return

        traverse_type = self.traverse_type.currentText()
        min_time = self.traverse_time_min.value()
        max_time = self.traverse_time_max.value()
        traverse_time = random.uniform(min_time, max_time)
        self.selected_traverse_time_label.setText(f"本次歷遍時間：{traverse_time:.2f} 秒")

        start_interval = self.start_interval.value() / 1000.0
        end_interval = self.end_interval.value() / 1000.0
        draw_count = self.draw_count.value()

        available_indices = [i for i in range(len(self.employees)) if i not in self.excluded_indices]

        if not available_indices:
            QMessageBox.information(self, "提示", "所有員工都已中獎")
            return

        self.lottery_thread = LotteryThread(
            self.employees,
            traverse_type,
            traverse_time,
            start_interval,
            end_interval,
            self.excluded_indices,
            draw_count
        )
        self.lottery_thread.update_highlight.connect(self.update_highlight)
        self.lottery_thread.draw_finished.connect(self.draw_finished)
        self.lottery_thread.start()

    def update_highlight(self, idx):
        self.employee_pool.highlighted = idx
        self.employee_pool.update()

    def draw_finished(self, winners):
        if winners:
            for winner in winners:
                idx = self.employees.index(winner)
                self.excluded_indices.append(idx)
                self.winners.append(winner)
                self.employee_pool.winners.append(idx)

            self.employee_pool.highlighted = None
            self.employee_pool.update()

            for winner in winners:
                self.winner_list.addItem(winner)
        else:
            QMessageBox.information(self, "提示", "沒有可抽取的員工")

    def closeEvent(self, event):
        if self.lottery_thread and self.lottery_thread.isRunning():
            self.lottery_thread.terminate()
        event.accept()


def load_rewards(rewards_folder='rewards'):
    rewards = {}
    for filename in os.listdir(rewards_folder):
        if filename.endswith('.txt'):
            with open(os.path.join(rewards_folder, filename), 'r', encoding='utf-8') as f:
                employees = [line.strip() for line in f if line.strip()]
                rewards[filename[:-4]] = employees
    return rewards


if __name__ == '__main__':
    app = QApplication(sys.argv)
    rewards = load_rewards()
    if not rewards:
        QMessageBox.critical(None, "錯誤", "未找到任何獎項清單，請檢查 rewards 資料夾")
        sys.exit(1)
    lottery_app = LotteryApp(rewards)
    lottery_app.show()
    sys.exit(app.exec_())