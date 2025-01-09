"""
The dearpygui lock doing with dpg.mutex() has the problem that other
threads also trying to lock the UI thread will just freeze permanently if it is already acquired.
So, this function puts a normal python lock around that lock to prevent that from happening
"""
from contextlib import contextmanager
import threading
import dearpygui.dearpygui as dpg

DPG_GLOBAL_LOCK = threading.RLock()
@contextmanager
def dpg_lock():
    yield "Nothin"
    # with DPG_GLOBAL_LOCK:
    #     yield "Nothin"
        # yield dpg.lock_mutex()
        # dpg.unlock_mutex()
