"""Double-click to open Bitwig Remote (native Qt app, no console window). Same as:  python manage.py app"""
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

from bwapp.main import run  # noqa: E402

sys.exit(run())
