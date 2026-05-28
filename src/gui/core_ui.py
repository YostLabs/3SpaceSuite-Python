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
        self.current_view: StagedView = None
    
    def set_view(self, staged_view: StagedView):
        if self.current_view is not None:
            dpg.delete_item(self.viewport, children_only=True)
            self.current_view.notify_closed(staged_view)
        if staged_view is not None:
            staged_view.submit(self.viewport)
            staged_view.notify_opened(self.current_view)
        self.current_view = staged_view

#Basically the same as a Dynamic Viewport just its a regular window instead of a child window and has some additional options
class DpgWizardViewer:

    def __init__(self, always_centered=False, modal=True, **kwargs):
        if "no_close" not in kwargs:
            kwargs["no_close"] = True
        if "autosize" not in kwargs:
            kwargs["autosize"] = True

        self.cur_window: StagedView = None
        with dpg.window(modal=modal, no_move=True, no_resize=True, no_collapse=True, **kwargs) as self.modal:
            pass
        
        self.page_destination = self.modal

        self.visible_handler = None
        if always_centered:
            with dpg.item_handler_registry() as self.visible_handler:
                dpg.add_item_visible_handler(callback=center_window_handler_callback, user_data=self.modal)
            dpg.bind_item_handler_registry(self.modal, self.visible_handler)

    def set_page_destination(self, destination):
        self.page_destination = destination

    def set_window(self, window: StagedView):
        if self.cur_window is not None:
            self.cur_window.notify_closed(window)
            dpg.delete_item(self.page_destination, children_only=True)
        if window is not None:
            window.submit(self.page_destination)
            window.notify_opened(self.cur_window)
        self.cur_window = window
    
    def delete(self):
        if self.visible_handler is not None:
            dpg.delete_item(self.visible_handler)
        dpg.delete_item(self.modal)

class DpgWizard(DpgWizardViewer):

    def __init__(self, always_centered=True, modal=True, **kwargs):
        super().__init__(always_centered=always_centered, modal=modal, **kwargs)

        self.page_index = -1
        self.pages: list[DpgWizardPageEmpty] = []

        self.cur_window: DpgWizardPageEmpty

    def go_next_page(self):
        if self.page_index < len(self.pages) - 1:
            if self.cur_window is not None:
                response = self.cur_window.on_next()
                if response is False:
                    return
            self.set_page(self.page_index + 1)
    
    def go_previous_page(self):
        if self.page_index > 0:
            if self.cur_window is not None:
                response = self.cur_window.on_back()
                if response is False:
                    return
            self.set_page(self.page_index - 1)

    @property
    def on_last_page(self):
        return self.page_index == len(self.pages) - 1

    @property
    def on_first_page(self):
        return self.page_index == 0

    def set_page(self, page_index: int):
        if page_index < 0 or page_index >= len(self.pages):
            return
        self.page_index = page_index
        self.set_window(self.pages[page_index])

    def add_page(self, page: "DpgWizardPageEmpty"):
        page.wizard = self
        page.ensure_view()
        self.pages.append(page)

    def set_window(self, window: "DpgWizardPageEmpty"):
        super().set_window(window)

    def close(self):
        for page in self.pages:
            page.delete()
        self.delete()

    def finish(self):
        self.close()

    def cancel(self):
        self.close()

class DpgWizardPageEmpty(StagedView):

    def __init__(self):
        super().__init__()

        # This will be set by the add page call in the wizard.
        # This allows the page to call methods on the wizard such as go_next_page or 
        #   go_previous_page without needing to worry about how the page is being used
        self.wizard: DpgWizard = None
        self._stage_id = None

    def create_view(self):
        """
        Returns the parent container that a subclass should put its content into.
        If no additional content is expected to be added to the page layout, return
        None (or just don't return anything)
        """
        self._stage_id = dpg.add_stage()
        return self._stage_id

    def ensure_view(self):
        if self._stage_id is None:
            self.create_view()

    def on_next(self):
        pass

    def on_back(self):
        pass

class DpgWizardPageBasic(DpgWizardPageEmpty):

    def __init__(self, title: str = "Title", width=-1, height=-1,
                 next_button_label: str = "Next", back_button_label: str = "Back", 
                 auto_finish: bool = True, auto_cancel: bool = True,
                 **kwargs):
        super().__init__()

        self.title = title
        self.width = width
        self.height = height
        self.next_button_label = next_button_label
        self.back_button_label = back_button_label
        self.back_button = None
        self.next_button = None
        self.auto_finish = auto_finish
        self.auto_cancel = auto_cancel

        self.kwargs = kwargs
    
    def create_view(self):
        dpg.push_container_stack(super().create_view())
        with dpg.child_window(width=self.width, height=self.height, border=False, **self.kwargs) as self.basic_window:
            #Title Space
            if self.title is not None:
                self.title_text = dpg.add_text(self.title, color=(120, 170, 255))
                dpg.add_separator()
                dpg.add_spacer(height=8)
            
            #User Space
            with dpg.child_window(height=-48, border=False) as self.user_space:
                pass
            
            #Footer Next/Back Buttons
            if self.next_button_label is not None or self.back_button_label is not None:
                dpg.add_spacer(height=8)
                dpg.add_separator()

                with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False, borders_innerV=False, borders_outerV=False):
                    dpg.add_table_column()
                    dpg.add_table_column(width_fixed=True, init_width_or_weight=150)
                    with dpg.table_row():
                        dpg.add_table_cell()
                        with dpg.group(horizontal=True):
                            self.back_button = dpg.add_button(
                                label=self.back_button_label, 
                                callback=self._back_button_pressed, 
                                width=70)
                            self.next_button = dpg.add_button(
                                label=self.next_button_label, 
                                callback=self._next_button_pressed, 
                                width=70)
        dpg.pop_container_stack()

        return self.user_space

    def _next_button_pressed(self, sender, app_data, user_data):
        if self.auto_finish and self.wizard.on_last_page:
            #Check the on_next response before finishing to allow the page to still have its own interaction first
            response = self.on_next()
            if response is False:
                return
            self.wizard.finish()
        else:
            self.wizard.go_next_page()
    
    def _back_button_pressed(self, sender, app_data, user_data):
        if self.auto_cancel and self.wizard.on_first_page:
            self.wizard.cancel()
        else:   
            self.wizard.go_previous_page()

    def notify_opened(self, old_view):
        super().notify_opened(old_view)
        if self.next_button is not None:
            if self.wizard.on_last_page:
                dpg.configure_item(self.next_button, label="Finish")
            else:
                dpg.configure_item(self.next_button, label=self.next_button_label)
        
        if self.back_button is not None:
            if self.wizard.on_first_page:
                dpg.configure_item(self.back_button, label="Cancel")
            else:
                dpg.configure_item(self.back_button, label=self.back_button_label)
