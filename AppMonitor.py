# -*- coding: utf-8 -*-
from datetime import datetime as dt
import ctypes
import logging
import logging.handlers
import os
import sys
import threading
import time

from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem
import click
import darkdetect as dd
import psutil

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from ImageViewer import ImageViewer
from getVRAMInfo import get_vram_usages

APP_NAME = 'AppMonitor'

# --- 設定項目 ---
PPROCESS_ID = None
PROCESS_NAME = None
CHECK_INTERVAL = 60             # 監視間隔 (秒)
SPAN_LENGTH = 0                 # 0: 全期間
# ----------------
PreferredAppMode = {
    'Light': 0,
    'Dark': 1,
}
# https://github.com/moses-palmer/pystray/issues/130
ctypes.windll['uxtheme.dll'][135](PreferredAppMode[dd.theme()])


class MonitorApp:
    def __init__(self):
        self.stop_event = threading.Event()
        self.app = None
        self.filename = str()
        # 初期状態は表示
        self.graph = True
        self.viewer = None
        self.logger = None

    def get_total_memory_usage(self, process_name):
        """指定した名前のプロセス（および子プロセス）の合計メモリ使用量(MB)を取得"""
        total_mem = 0
        for proc in psutil.process_iter(['name', 'memory_info']):
            try:
                if proc.info['name'].lower() == process_name.lower():
                    total_mem += proc.info['memory_info'].rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return total_mem / (1024 * 1024)

    def get_total_vram_usage(self, process_name):
        usages = get_vram_usages()
        usage = usages[process_name] if process_name in usages else 0
        return usage / (1024 * 1024)

    def monitor_loop(self):
        while not self.stop_event.is_set():
            start_time = time.time()
            mem_usage = self.get_total_memory_usage(PROCESS_NAME)
            vram_usage = self.get_total_vram_usage(PROCESS_NAME)
            title = f'{PROCESS_NAME} {int(mem_usage)} MB {int(vram_usage)} MB'
            self.logger.info(title)
            self.app.title = title
            self.plot()
            elapsed = time.time() - start_time

            if self.stop_event.wait(CHECK_INTERVAL - elapsed):
                break

    def viewer_loop(self):
        while True:
            if os.path.exists(self.filename):
                break
            time.sleep(1)

        self.viewer = ImageViewer(self.filename)
        self.viewer.mainloop()

    def toggle_graph(self):
        self.graph = not self.graph
        if self.graph:
            self.show_graph()
        else:
            self.hide_graph()

    def show_graph(self):
        if self.viewer:
            self.viewer.show_window()

    def hide_graph(self):
        if self.viewer:
            self.viewer.withdraw()

    def create_image(self):
        width, height = 64, 64
        image = Image.new('RGB', (width, height), (0, 0, 0))
        dc = ImageDraw.Draw(image)
        dc.ellipse([10, 10, 54, 54], fill=(214, 120, 215))
        return image

    def plot(self):
        length = SPAN_LENGTH

        time_data = {}
        vram_data = {}
        basename = os.path.splitext(PROCESS_NAME)[0]
        with open(f'log_{basename}.log') as fd:
            lines = fd.read().splitlines()
            if length == 0:
                length = len(lines)
            for line in lines[len(lines) - length:]:
                tmp = line.split()
                if tmp and tmp[2] == '[INFO]':
                    # 0          1        2      3       4   5  6    7
                    # 2026/10/31 21:14:25 [INFO] run.exe 231 MB 1920 MB
                    _time = dt.strptime(f'{tmp[0]} {tmp[1]}', '%Y/%m/%d %H:%M:%S')
                    time_data[_time] = int(tmp[4])
                    if len(tmp) >= 7:
                        vram_data[_time] = int(tmp[6])

        if time_data:
            #
            # いろいろ調整中
            #

            # 上下左右余白なし
            mpl.rcParams['axes.xmargin'] = 0
            mpl.rcParams['axes.ymargin'] = 0

            xs = time_data.keys()
            ys = [time_data[tim] for tim in xs]
            vys = [vram_data[tim] if tim in vram_data else 0 for tim in xs]

            ymax = max(max(ys), max(vys))

            fig, ax = plt.subplots(figsize=(10, 5))
            ax.set_ylim(0, int(ymax) * 1.1)
            ax.set_ylabel('Memory (MB)', color='b')
            ax.plot(xs, ys, color='b')

            ax2 = ax.twinx()
            ax2.set_ylim(0, int(ymax * 1.1))
            ax2.set_ylabel('VRAM (MB)', color='tab:orange')
            ax2.plot(xs, vys, label='VRAM', color='tab:orange')

            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
            fig.autofmt_xdate()

            plt.title(f'Memory Consumption {PROCESS_NAME}')
            plt.grid(True)
            plt.tight_layout()

            self.filename = f'Fig_{basename}.png'
            plt.savefig(self.filename)
            plt.close()

    def stopApp(self, icon, item):
        self.stop_event.set()
        self.app.stop()

    def runApp(self):
        threading.Thread(target=self.monitor_loop, daemon=True).start()
        threading.Thread(target=self.viewer_loop, daemon=True).start()

        # システムトレイアイコンの設定
        self.app = Icon(APP_NAME)
        self.app.menu = Menu(
            MenuItem(f'{PROCESS_NAME} を監視中...', self.toggle_graph, default=True),
            MenuItem('Show', self.show_graph),
            MenuItem('Hide', self.hide_graph),
            MenuItem('Exit', self.stopApp)
        )
        self.app.icon = self.create_image()
        self.app.run()


@click.command(help='Application Memory Monitor')
@click.option('-i', '--interval', type=int, default=60, help='chech interval (seconds)')
@click.option('-l', '--length', type=int, default=0, help='graph span length')
@click.option('-n', '--name', type=str, default=str(), help='target process name (ex. chrome.exe)')
@click.option('-p', '--pid', type=int, default=0, help='target process ID')
def run(pid, name, interval, length):
    global PROCESS_ID, PROCESS_NAME, CHECK_INTERVAL, SPAN_LENGTH

    PROCESS_ID = pid
    PROCESS_NAME = name
    CHECK_INTERVAL = interval
    SPAN_LENGTH = length

    if not PROCESS_NAME and not PROCESS_ID:
        print('Neither --pid nor --name specified', file=sys.stderr)
        exit(1)
    else:
        if PROCESS_ID and not PROCESS_NAME:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['pid'] == PROCESS_ID:
                    PROCESS_NAME = proc.info['name']
                    break

        # logger settings
        logging.basicConfig(
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.handlers.RotatingFileHandler(f'log_{PROCESS_NAME.replace(".exe", "")}.log', encoding='utf-8', maxBytes=1000000, backupCount=0),
                logging.StreamHandler(),
            ],
            datefmt='%Y/%m/%d %X'
        )
        app = MonitorApp()
        app.logger = logging.getLogger(PROCESS_NAME)
        app.logger.setLevel(logging.DEBUG)
        app.runApp()


if __name__ == '__main__':
    run()
