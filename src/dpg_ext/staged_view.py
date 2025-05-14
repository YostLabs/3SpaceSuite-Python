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
        return self

    """
    This is just a way to notify the staged view it is being closed
    and should have its own implementation on each object inheriting from StagedView.
    This does NOT actually remove the stage from view, it is up to the caller to do that.
    This is purely to notify the stage it is being closed so windows can have close events.
    """
    def notify_closed(self, new_view: "StagedView"): ...

    """
    Same as close but for opening
    """
    def notify_opened(self, old_view: "StagedView"): ...

    def delete(self):
        with dpg_lock():
            for slot in dpg.get_item_children(self._stage_id):
                for child in dpg.get_item_children(self._stage_id, slot):
                    dpg.delete_item(child)
            dpg.delete_item(self._stage_id)

class StagedTabManager(StagedView):

    def __init__(self):
        self.staged_view_dict: dict[int,StagedView] = None
        self.deleted = False
        self.open_tab = None
        self.tab_bar = None

    def add_tab(self, view: StagedView, tab: int = None):
        if tab is None:
            tab = dpg.top_container_stack()
        if self.staged_view_dict is None: self.staged_view_dict = {}
        self.staged_view_dict[tab] = view

    def set_open_tab(self, tab: int):
        self.open_tab = tab
        if self.tab_bar is not None:
            #Have to initialize the tab value for DPG to track it
            #Visuals will work without this, but dpg.get_value() on notify_opened would not
            dpg.set_value(self.tab_bar, tab)

    def set_tab_bar(self, tab_bar: int = None):
        """
        Call before set_open_tab
        """
        if tab_bar is None:
            tab_bar = dpg.top_container_stack()
        self.tab_bar = tab_bar
        dpg.set_item_callback(tab_bar, self.__tab_callback)

    def notify_opened(self, old_view: StagedView):
        if self.deleted or self.staged_view_dict is None: return
        self.staged_view_dict[dpg.get_value(self.tab_bar)].notify_opened(old_view)

    def notify_closed(self, new_view: StagedView):
        if self.deleted or self.staged_view_dict is None: return
        self.staged_view_dict[dpg.get_value(self.tab_bar)].notify_closed(new_view)

    def __tab_callback(self, sender, app_data, user_data):
        if self.deleted: return
        new_view = self.staged_view_dict[app_data]
        old_view = self.staged_view_dict[self.open_tab]
        if self.open_tab is not None and self.open_tab != app_data:
            self.staged_view_dict[self.open_tab].notify_closed(new_view)
        self.open_tab = app_data
        self.staged_view_dict[app_data].notify_opened(old_view)
    
    def delete(self):
        if self.staged_view_dict is not None:
            for window in self.staged_view_dict.values():
                window.delete()
        super().delete()
        self.deleted = True