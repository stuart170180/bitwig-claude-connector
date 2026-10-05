"""Double-click to open Bitwig Remote (no console window). Same as:  python manage.py app"""
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())
sys.argv = [sys.argv[0]] + sys.argv[1:]

from bwmcp.monitor import desktop  # noqa: E402

desktop.open_window(on_top="--top" in sys.argv)
