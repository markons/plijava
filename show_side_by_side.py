#!/usr/bin/env python3
"""
Simple Tk GUI to show a PL/I source file and the generated Java side-by-side.

Usage:
  python show_side_by_side.py --pli path/to/file.pli --java path/to/file.java

If either argument is omitted you can open files from the GUI.
"""
import argparse
import tkinter as tk
from tkinter import filedialog, font
import os


def read_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"*** Error reading {path}: {e}\n"


class SideBySideViewer(tk.Tk):
    def __init__(self, pli_path=None, java_path=None):
        super().__init__()
        self.title('PL/I ↔ Java viewer')
        self.geometry('1200x700')

        self.paned = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=1)

        left_frame = tk.Frame(self.paned)
        right_frame = tk.Frame(self.paned)

        self.paned.add(left_frame)
        self.paned.add(right_frame)

        header_font = font.Font(weight='bold')
        mono = font.Font(family='Courier', size=10)

        # Left: PL/I
        tk.Label(left_frame, text='PL/I source', font=header_font).pack(anchor='w')
        self.pli_text = tk.Text(left_frame, wrap='none', font=mono)
        pli_scroll_y = tk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.pli_text.yview)
        pli_scroll_x = tk.Scrollbar(left_frame, orient=tk.HORIZONTAL, command=self.pli_text.xview)
        self.pli_text.configure(yscrollcommand=pli_scroll_y.set, xscrollcommand=pli_scroll_x.set)
        self.pli_text.pack(fill=tk.BOTH, expand=1, side=tk.LEFT)
        pli_scroll_y.pack(fill=tk.Y, side=tk.RIGHT)
        pli_scroll_x.pack(fill=tk.X, side=tk.BOTTOM)

        # Right: Java
        tk.Label(right_frame, text='Generated Java', font=header_font).pack(anchor='w')
        self.java_text = tk.Text(right_frame, wrap='none', font=mono)
        java_scroll_y = tk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.java_text.yview)
        java_scroll_x = tk.Scrollbar(right_frame, orient=tk.HORIZONTAL, command=self.java_text.xview)
        self.java_text.configure(yscrollcommand=java_scroll_y.set, xscrollcommand=java_scroll_x.set)
        self.java_text.pack(fill=tk.BOTH, expand=1, side=tk.LEFT)
        java_scroll_y.pack(fill=tk.Y, side=tk.RIGHT)
        java_scroll_x.pack(fill=tk.X, side=tk.BOTTOM)

        # Controls
        ctrl_frame = tk.Frame(self)
        ctrl_frame.pack(fill=tk.X)
        tk.Button(ctrl_frame, text='Open PL/I file...', command=self.open_pli).pack(side=tk.LEFT, padx=4, pady=4)
        tk.Button(ctrl_frame, text='Open Java file...', command=self.open_java).pack(side=tk.LEFT, padx=4, pady=4)
        tk.Button(ctrl_frame, text='Reload', command=self.reload).pack(side=tk.LEFT, padx=4, pady=4)
        tk.Button(ctrl_frame, text='Close', command=self.destroy).pack(side=tk.RIGHT, padx=4, pady=4)

        self.pli_path = pli_path
        self.java_path = java_path
        if pli_path:
            self.load_pli(pli_path)
        if java_path:
            self.load_java(java_path)

    def open_pli(self):
        path = filedialog.askopenfilename(title='Open PL/I file', filetypes=[('PL/I files', '*.pli'), ('All files', '*.*')])
        if path:
            self.pli_path = path
            self.load_pli(path)

    def open_java(self):
        path = filedialog.askopenfilename(title='Open Java file', filetypes=[('Java files', '*.java'), ('All files', '*.*')])
        if path:
            self.java_path = path
            self.load_java(path)

    def load_pli(self, path):
        self.pli_text.config(state=tk.NORMAL)
        self.pli_text.delete('1.0', tk.END)
        self.pli_text.insert(tk.END, read_file(path))
        self.pli_text.config(state=tk.DISABLED)

    def load_java(self, path):
        self.java_text.config(state=tk.NORMAL)
        self.java_text.delete('1.0', tk.END)
        self.java_text.insert(tk.END, read_file(path))
        self.java_text.config(state=tk.DISABLED)

    def reload(self):
        if self.pli_path:
            self.load_pli(self.pli_path)
        if self.java_path:
            self.load_java(self.java_path)


def main():
    parser = argparse.ArgumentParser(description='Show PL/I and generated Java side-by-side')
    parser.add_argument('--pli', help='PL/I source file')
    parser.add_argument('--java', help='Generated Java file')
    args = parser.parse_args()

    if not args.pli and not args.java:
        parser.print_help()
        print()

    app = SideBySideViewer(pli_path=args.pli, java_path=args.java)
    app.mainloop()


if __name__ == '__main__':
    main()
