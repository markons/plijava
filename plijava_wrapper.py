"""
Wrapper that runs plijava.py on a specific .pli file without opening the
tkinter file dialog.  Usage:  python plijava_wrapper.py <path/to/file.pli>
"""
import sys
import os

pli_file = os.path.abspath(sys.argv[1])

# --- patch tkinter BEFORE plijava.py imports it ---
import tkinter
import tkinter.filedialog

class _MockTk:
    def __init__(self): pass
    def withdraw(self): pass
    def destroy(self): pass

tkinter.Tk = _MockTk
tkinter.filedialog.askopenfilename = lambda **kwargs: pli_file

# --- run plijava from its own directory so javac output lands there ---
os.chdir(r'F:\plijava')

with open(r'F:\plijava\plijava.py', 'r', encoding='utf-8') as f:
    src = f.read()

exec(compile(src, 'plijava.py', 'exec'), {'__name__': '__main__', '__file__': 'plijava.py'})
