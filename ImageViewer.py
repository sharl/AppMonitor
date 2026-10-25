# -*- coding: utf-8 -*-
import os
import time

from PIL import Image, ImageTk
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
import tkinter as tk


class ImageChangeHandler(FileSystemEventHandler):
    def __init__(self, callback, target_path):
        self.callback = callback
        self.target_path = os.path.abspath(target_path)

    def on_modified(self, event):
        if os.path.abspath(event.src_path) == self.target_path:
            time.sleep(0.1)
            self.callback()


class ImageViewer(tk.Tk):
    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path

        self.overrideredirect(True)
        self.attributes('-topmost', False)
        self.configure(bg='black')
        self.withdraw()

        self.zoom_level = 1.0
        self.is_fit_mode = False
        self.original_img = None
        self.topmost_var = tk.BooleanVar(value=False)

        self.label = tk.Label(self, bg='black')
        self.label.pack(expand=True, fill='both')

        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_checkbutton(label='Always on Top', variable=self.topmost_var, command=self.sync_topmost)
        self.context_menu.add_command(label='Fit (F)', command=self.toggle_fit)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='Hide', command=self.withdraw)
        # self.context_menu.add_command(label='終了 (Esc)', command=self.quit_app)

        # self.bind('<Escape>', lambda e: self.quit_app())
        self.bind('f', lambda e: self.toggle_fit())
        self.label.bind('<Button-3>', self.show_context_menu)
        self.label.bind('<Button-1>', self.start_move)
        self.label.bind('<B1-Motion>', self.do_move)
        self.bind('<MouseWheel>', self.handle_zoom)

        self.load_image()
        self.start_watching()
        self.deiconify()

    def load_image(self):
        if not os.path.exists(self.image_path):
            return
        try:
            with Image.open(self.image_path) as img:
                self.original_img = img.copy()
            self.refresh_display()
        except Exception as e:
            print(f'Load Error: {e}')

    def refresh_display(self):
        if self.original_img is None:
            return

        orig_w, orig_h = self.original_img.size
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()

        if self.is_fit_mode:
            ratio = min(sw / orig_w, sh / orig_h)
            nw, nh = int(orig_w * ratio), int(orig_h * ratio)
            self.geometry(f'{nw}x{nh}+{(sw-nw)//2}+{(sh-nh)//2}')
        else:
            nw, nh = int(orig_w * self.zoom_level), int(orig_h * self.zoom_level)
            self.geometry(f'{max(nw, 1)}x{max(nh, 1)}')

        resized = self.original_img.resize((max(nw, 1), max(nh, 1)), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(resized)
        self.label.config(image=self.photo)

    def handle_zoom(self, event):
        self.zoom_level *= 1.1 if event.delta > 0 else 0.9
        self.is_fit_mode = False
        self.refresh_display()

    def toggle_fit(self):
        self.is_fit_mode = not self.is_fit_mode
        if not self.is_fit_mode:
            self.zoom_level = 1.0
        self.refresh_display()

    def sync_topmost(self):
        self.attributes('-topmost', self.topmost_var.get())

    def start_move(self, event):
        self._drag_data = {'x': event.x, 'y': event.y}

    def do_move(self, event):
        dx, dy = event.x - self._drag_data['x'], event.y - self._drag_data['y']
        self.geometry(f'+{self.winfo_x() + dx}+{self.winfo_y() + dy}')

    def show_context_menu(self, event):
        self.context_menu.post(event.x_root, event.y_root)

    def show_window(self):
        self.after(0, self.deiconify)
        self.after(0, lambda: self.attributes('-topmost', True))

    def start_watching(self):
        event_handler = ImageChangeHandler(lambda: self.after(0, self.load_image), self.image_path)
        self.observer = Observer()
        self.observer.schedule(event_handler, os.path.dirname(os.path.abspath(self.image_path)), recursive=False)
        self.observer.start()

    def quit_app(self):
        self.observer.stop()
        self.destroy()


if __name__ == '__main__':
    import sys

    path = str()
    if len(sys.argv) > 1:
        path = sys.argv[1]
    if os.path.exists(path):
        app = ImageViewer(path)
        app.mainloop()
    else:
        print(f'File not found: {path}')
