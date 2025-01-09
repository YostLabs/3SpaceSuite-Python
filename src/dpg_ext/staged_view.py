import dearpygui.dearpygui as dpg
from dpg_ext.global_lock import dpg_lock
"""
A way to make dearpygui more object oriented.
Simplifies the creation of objects based around staging
"""


class StagedView:
    """
    Classes that implement this should have
    a stage object assigned to self._stage_id
    """

    def submit(self, parent = None):
        if parent is not None:
            dpg.push_container_stack(parent)
        dpg.unstage(self._stage_id)
        if parent is not None:
            dpg.pop_container_stack()

    """
    This is just a way to notify the staged view it is being closed
    and should have its own implementation on each object inheriting from StagedView.
    This does NOT actually remove the stage from view, it is up to the caller to do that.
    This is purely to notify the stage it is being closed so windows can have close events.
    """
    def notify_closed(self): ...

    """
    Same as close but for opening
    """
    def notify_opened(self): ...

    def delete(self):
        with dpg_lock():
            for slot in dpg.get_item_children(self._stage_id):
                for child in dpg.get_item_children(self._stage_id, slot):
                    dpg.delete_item(child)
            dpg.delete_item(self._stage_id)