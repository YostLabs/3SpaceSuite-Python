import dearpygui.dearpygui as dpg
from dpg_ext.extension_functions import center_window_handler_callback

from typing import Callable

class PopupButton:

    def __init__(self, label: str = "", callback: Callable = None, close_on_select=False, **kwargs):
        self.label = label
        self.callback = callback
        self.close_on_select = close_on_select
        self.kwargs = kwargs

class PopupWindow:
    """
    A helper class for creating frequently used popups that
    also manages their lifetime and allows reconfiguring to avoid
    requiring the awkward delay between showing modal windows.
    """

    def __init__(self, title=None, width=350, always_center=True, no_close=False, **kwargs):
        with dpg.window(label=title, modal=True, no_resize=True, show=True, 
                        width=width, autosize=False,
                        no_move=always_center, no_close=no_close, on_close=self.__on_close, no_title_bar=not title, 
                        **kwargs) as self.window:
            self.text_group = dpg.add_group()
            self.loading_group = dpg.add_group()
            self.custom_group = dpg.add_group()
            self.button_group = dpg.add_group()
            
        #Handle centering the window
        self.visible_handler = None
        if always_center:
            with dpg.item_handler_registry() as self.visible_handler:
                dpg.add_item_visible_handler(callback=center_window_handler_callback, user_data=self.window)
            dpg.bind_item_handler_registry(self.window, self.visible_handler)
    
    def configure(self, **kwargs):
        if "height" in kwargs:
            dpg.set_item_height(self.window, kwargs["height"])
            del kwargs["height"]
        dpg.configure_item(self.window, **kwargs)

    def add_buttons(self, buttons: list[PopupButton]):
        def __on_select(sender, app_data, user_data):
            button: PopupButton = user_data

            if button.close_on_select:
                self.delete()
            
            if button.callback is not None:
                button.callback()

        dpg.push_container_stack(self.button_group)
        with dpg.group(horizontal=True):
            for button in buttons:
                dpg.add_button(label=button.label, callback=__on_select, user_data=button, **button.kwargs)
        dpg.pop_container_stack()

        return self

    def add_text(self, text: str):
        dpg.push_container_stack(self.text_group)
        dpg.add_text(text, wrap=dpg.get_item_width(self.window))
        dpg.pop_container_stack()

        return self
    
    def add_loading_wheel(self):
        #Because of this bug https://github.com/hoffstadt/DearPyGui/issues/2500#issuecomment-2797531732
        dpg.configure_item(self.window, autosize=False)
        dpg.push_container_stack(self.window)
        with dpg.table(header_row=False, width=dpg.get_item_width(self.window)):
            dpg.add_table_column()
            dpg.add_table_column(init_width_or_weight=70, width_fixed=True)
            dpg.add_table_column()
            with dpg.table_row():
                dpg.add_table_cell()
                dpg.add_loading_indicator()
        dpg.pop_container_stack()
        
        return self

    def delete(self):
        dpg.delete_item(self.window)
        if self.visible_handler is not None:
            dpg.delete_item(self.visible_handler)
            self.visible_handler = None

    def clear(self):
        dpg.delete_item(self.window, children_only=True)
        #To undo the fix to this bug when using a loading indicator
        #https://github.com/hoffstadt/DearPyGui/issues/2500#issuecomment-2797531732
        dpg.configure_item(self.window, autosize=False)        
        dpg.push_container_stack(self.window)
        self.text_group = dpg.add_group()
        self.loading_group = dpg.add_group()
        self.custom_group = dpg.add_group()
        self.button_group = dpg.add_group()
        dpg.pop_container_stack()

    def set_autosize(self, enabled=True):
        """
        Autosize is useful, especially when keeping the same popup window and changing its contents.
        However, there are times this needs to be disabled due to the following bug. Sadly, there does not
        seem to be a one size fits all fix right now, so the user may have to manually manage this state when
        creating and modifiying popups. If your popup starts growing, disable this.
        https://github.com/hoffstadt/DearPyGui/issues/2500#issuecomment-2797531732
        """
        dpg.configure_item(self.window, autosize=enabled)

    def set_confirm_box(self, text: str = "", title: str="Confirmation", on_cancel: Callable = None, on_confirm: Callable = None, close_on_selection: bool = True, confirm_text="Confirm", cancel_text="Cancel"):
        self.clear()
        dpg.configure_item(self.window, label=title)
        if text:
            self.add_text(text)

        self.add_buttons([PopupButton(label=confirm_text, callback=on_confirm, close_on_select=True), 
                          PopupButton(label=cancel_text, callback=on_cancel, close_on_select=True)])
        
        return self
    
    def set_message_box(self, text: str = "", title: str = ""):
        self.clear()
        dpg.configure_item(self.window, label=title)
        dpg.configure_item(self.window, autosize=True)
        self.add_text(text)
        self.add_buttons([PopupButton("Ok", close_on_select=True)])

        return self

    def __enter__(self):
        dpg.push_container_stack(self.custom_group)
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        dpg.pop_container_stack()
        return False

    def __on_close(self):
        self.delete()
        
if __name__ == "__main__":
    dpg.create_context()
    dpg.create_viewport()

    def spawn_window():
        my_popup = PopupWindow("My Window").set_confirm_box(text="Erase settings?", on_confirm=lambda: print("Confirmed"), on_cancel=lambda: print("Canceled"))

    with dpg.window() as primary_window:
        dpg.add_button(label="Click Me", callback=spawn_window)

    dpg.show_item_registry()

    dpg.set_primary_window(primary_window, True)

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()