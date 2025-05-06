from managers.resource_manager import *
from dpg_ext.selectable_button import SelectableButton
from dpg_ext.staged_view import StagedView
from dpg_ext.extension_functions import center_window_handler_callback
import dearpygui.dearpygui as dpg

class FontManager:

    DEFAULT_FONT = None
    DEFAULT_FONT_LARGE = None

    COMIC_FONT = None
    COMIC_FONT_LARGE = None

    COURIER_FONT = None
    COURIER_FONT_LARGE = None

    FIRA_FONT_SMALL = None
    FIRA_FONT = None
    FIRA_FONT_LARGE = None

    @classmethod
    def init(cls):
        with dpg.font_registry():
            print(f"{FONT_FOLDER=}")
            cls.COMIC_FONT = dpg.add_font(FONT_FOLDER / "comic.ttf", 18)
            
            cls.COMIC_FONT_LARGE = dpg.add_font(FONT_FOLDER / "comic.ttf", 50)

            cls.COURIER_FONT = dpg.add_font(FONT_FOLDER / "cour.ttf", 18)
            cls.COURIER_FONT_LARGE = dpg.add_font(FONT_FOLDER / "cour.ttf", 50)

            cls.FIRA_FONT_SMALL = dpg.add_font(FONT_FOLDER / "FiraCode-Regular.ttf", 12)
            cls.FIRA_FONT = dpg.add_font(FONT_FOLDER / "FiraCode-Regular.ttf", 18)
            cls.FIRA_FONT_LARGE = dpg.add_font(FONT_FOLDER / "FiraCode-Regular.ttf", 50)

            cls.DEFAULT_FONT = cls.FIRA_FONT
            cls.DEFAULT_FONT_LARGE = cls.FIRA_FONT_LARGE

class BannerMenu(StagedView):
    """
    Banner Menu is just a collection of
    Selectable Buttons that can be dynamically modified
    and also manages the single selection aspect of the buttons
    """

    def __init__(self, height=-2, container=None):
        self.banners: list[SelectableButton] = []
        
        with dpg.stage(label="BannerMenuStage") as self._stage_id:
            if container is None:
                    self.container = dpg.add_child_window(height=height, autosize_x=True, label="Banner Menu")
            else:
                self.container = container

        self.active_banner: SelectableButton = None

    def add_banner(self, banner: SelectableButton):
        self.banners.append(banner)
        banner.add_selected_callback(self.on_banner_selected)
        banner.submit(self.container)

    def remove_banner(self, banner: SelectableButton, auto_select=True):
        """
        Removes the passed banner from the banner list and deletes it.
        If auto_select is true, and the banner being removed is currently active,
        automatically set the first banner that was added as the active banner
        """
        self.banners.remove(banner)
        banner.delete()
        #In order for it to actually appear deleted, since the banner is staged and submitted instead of being standalone, must redraw
        self.__redraw_banners()

        if auto_select and banner == self.active_banner and len(self.banners) > 0:
            self.set_banner(self.banners[0])
    
    def get_banner_index(self, banner: SelectableButton):
        for i, b in enumerate(self.banners):
            if b is banner:
                return i
        return None
    
    def get_active_index(self):
        if self.active_banner is None: return None
        return self.get_banner_index(self.active_banner)
    
    def set_banner_index(self, banner: SelectableButton, index: int):
        if banner not in self.banners: return
        if index < 0 or index >= len(self.banners): return
        self.banners.remove(banner)
        self.banners.insert(index, banner)
        self.__redraw_banners()

    def set_banner(self, banner: SelectableButton):
        self.on_banner_selected(banner)
        if banner is not None:
            banner.set_selected()

    def on_banner_selected(self, selected_banner):
        for banner in self.banners:
            if banner is not selected_banner:
                banner.set_unselected()
        self.active_banner = selected_banner

    def __redraw_banners(self):
        dpg.delete_item(self.container, children_only=True)
        for banner in self.banners:
            banner.submit(self.container)

class DynamicViewport(StagedView):
    """
    This viewport allows loading different types of views
    into it and automatically handles cleaning up whatever
    is currently there, if anything
    """

    def __init__(self):
        with dpg.stage(label="Dynamic Viewport Stage") as self._stage_id:
            self.viewport = dpg.add_child_window(label="Viewport Window", height=-2)
        self.current_view = None
    
    def set_view(self, staged_view: StagedView):
        if self.current_view is not None:
            dpg.delete_item(self.viewport, children_only=True)
            self.current_view.notify_closed()
        if staged_view is not None:
            staged_view.submit(self.viewport)
            staged_view.notify_opened()
        self.current_view = staged_view

#Basically the same as a Dynamic Viewport just its a regular window instead of a child window and has some additional options
class DpgWizard:

    def __init__(self, always_centered=False, **kwargs):
        
        self.cur_window: StagedView = None
        with dpg.window(modal=True, no_move=True, no_resize=True, no_close=True, autosize=True, **kwargs) as self.modal:
            pass
        
        self.visible_handler = None
        if always_centered:
            with dpg.item_handler_registry() as self.visible_handler:
                dpg.add_item_visible_handler(callback=center_window_handler_callback, user_data=self.modal)
            dpg.bind_item_handler_registry(self.modal, self.visible_handler)

    def set_window(self, window: StagedView):
        if self.cur_window is not None:
            self.cur_window.notify_closed()
            dpg.delete_item(self.modal, children_only=True)
        if window is not None:
            window.submit(self.modal)
            window.notify_opened()
        self.cur_window = window
    
    def delete(self):
        if self.visible_handler is not None:
            dpg.delete_item(self.visible_handler)
        dpg.delete_item(self.modal)
