import dearpygui.dearpygui as dpg

"""
Simple Wrapper around the logger extension
to also set the desired theme

Mostly the same as dearpygui_ext import logger
however, it was changed to support the staging framework
I am going for instead of the immediate rendering
"""

class LogWindow:

    BASE_THEME = None

    MESSAGE_TYPES = ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    MESSAGE_THEMES = None

    def __init__(self, height=400, flush_count = 50):
        
        self.log_level = 0
        self._auto_scroll = True
        self.filter_id = None
        self.count = 0
        self.flush_count = flush_count
        self.wrap = 100 #Needs a default value in case adding text before first resize handler is called (Which will happen on submit)

        self.stage_id = dpg.add_stage(label="Log Window Stage")
        with dpg.group(horizontal=True, parent=self.stage_id) as self.group:
            dpg.add_checkbox(label="Auto-scroll", default_value=True, callback=lambda sender:self.auto_scroll(dpg.get_value(sender)))
            self.clear_button = dpg.add_button(label="Clear", callback=self.clear_log)

        self.filter_in = dpg.add_input_text(label="Filter", callback=lambda sender: dpg.set_value(self.filter_id, dpg.get_value(sender)), 
                    parent=self.stage_id)

        self.child_id = dpg.add_child_window(parent=self.stage_id, autosize_x=True, height=height)
        self.filter_id = dpg.add_filter_set(parent=self.child_id)

        with dpg.item_handler_registry() as self.resize_handler:
            dpg.add_item_resize_handler(callback=self.__on_resize)
        dpg.bind_item_handler_registry(self.filter_in, self.resize_handler)

        if LogWindow.MESSAGE_THEMES is None:
            #Makes the log text not so spaced out
            with dpg.theme(label="LogBaseTheme") as LogWindow.BASE_THEME:
                with dpg.theme_component(dpg.mvText):
                    dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 4, 0)
                    dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 0)

            with dpg.theme(label="LogTraceTheme") as trace_theme:
                with dpg.theme_component(0):
                    dpg.add_theme_color(dpg.mvThemeCol_Text, (0, 255, 0, 255))

            with dpg.theme(label="LogDebugTheme") as debug_theme:
                with dpg.theme_component(0):
                    dpg.add_theme_color(dpg.mvThemeCol_Text, (64, 128, 255, 255))

            with dpg.theme(label="LogInfoTheme") as info_theme:
                pass
                # with dpg.theme_component(0):
                #     dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))

            with dpg.theme(label="LogWarningTheme") as warning_theme:
                with dpg.theme_component(0):
                    dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 104, 37, 255))

            with dpg.theme(label="LogErrorTheme") as error_theme:
                with dpg.theme_component(0):
                    dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 0, 0, 255))

            with dpg.theme(label="LogCriticalTheme") as critical_theme:
                with dpg.theme_component(0):
                    dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 0, 255, 255))
        
            LogWindow.MESSAGE_THEMES = [trace_theme, debug_theme, info_theme, warning_theme, error_theme, critical_theme]

        dpg.bind_item_theme(self.child_id, LogWindow.BASE_THEME)

    def set_height(self, height):
        dpg.set_item_height(self.child_id, height)

    def submit(self, parent = None):
        if parent:
            self.window_id = parent
        else:
            self.window_id = dpg.add_window(label="mvLogger", pos=(200, 200), width=500, height=500)
        
        dpg.push_container_stack(self.window_id)
        dpg.unstage(self.stage_id)
        dpg.pop_container_stack()

    def auto_scroll(self, value):
        self._auto_scroll = value

    @classmethod
    def build_message_str(cls, message, level):
        return f"[{cls.MESSAGE_TYPES[level]}]\t\t" + message

    def _log(self, message, level):

        if level < self.log_level:
            return

        self.count+=1

        if self.count > self.flush_count:
            self.clear_oldest_item()

        message = self.build_message_str(message, level)
        theme = LogWindow.MESSAGE_THEMES[level]

        new_log = dpg.add_text(message, parent=self.filter_id, filter_key=message, wrap=self.wrap)
        dpg.bind_item_theme(new_log, theme)
        if self._auto_scroll:
            scroll_max = dpg.get_y_scroll_max(self.child_id)
            dpg.set_y_scroll(self.child_id, -1.0)

    def log(self, message):
        self._log(message, 0)

    def log_debug(self, message):
        self._log(message, 1)

    def log_info(self, message):
        self._log(message, 2)

    def log_warning(self, message):
        self._log(message, 3)

    def log_error(self, message):
        self._log(message, 4)

    def log_critical(self, message):
        self._log(message, 5)

    def clear_oldest_item(self):
        dpg.delete_item(dpg.get_item_children(self.filter_id, 1)[0])
        self.count -= 1
        
    def clear_log(self):
        dpg.delete_item(self.filter_id, children_only=True)
        self.count = 0

    def __on_resize(self, sender, app_data):
        width, _ = dpg.get_item_rect_size(self.child_id)
        self.wrap = width - 10
        for child in dpg.get_item_children(self.filter_id, 1):
            dpg.configure_item(child, wrap = self.wrap)

    def destroy(self):
        dpg.delete_item(self.resize_handler)
        dpg.delete_item(self.stage_id)

#Another type of log window, but restricted to just being a basic text field
#This is required for allowing text selection but also has a lot of limitations
import textwrap
class MultilineText:

    TEXT_THEME = None
    FRAME_PADDING = 3

    def __init__(self, width: int = -1, height: int = 400, max_messages=100):
        if MultilineText.TEXT_THEME is None:
            with dpg.theme(label="MultilineTextTheme") as MultilineText.TEXT_THEME:
                with dpg.theme_component(dpg.mvInputText):
                    dpg.add_theme_color(dpg.mvThemeCol_FrameBg, [0, 0, 0, 0], category=dpg.mvThemeCat_Core)

        self.width = width
        self.height = height
        self.messages: list[str] = [] #The original messages, so they can be modified on things like resize
        self.modified_messages: list[str] = [] #The wrapped messages
        self.cur_message: str = "" #The total text field
        self.max_messages = max_messages

        #Place holder, will be automatically updated when the window is created and the resize callback is called
        self.wrap_chars=1
        self.auto_scroll_enabled = True

        self.stage_id = dpg.add_stage(label="Log Window Stage")
        with dpg.group(horizontal=True, parent=self.stage_id) as self.group:
            self.scroll_checkbox = dpg.add_checkbox(label="Auto-scroll", default_value=True, callback=lambda s, a, u: self.auto_scroll(a))
            self.clear_button = dpg.add_button(label="Clear", callback=self.clear)

        if width != -1:
            self.child_window = dpg.add_child_window(parent=self.stage_id, width=width, height=height)
        else:
            self.child_window = dpg.add_child_window(parent=self.stage_id, autosize_x=True, height=height)

        #Auto scroll is handled by tracked.
        self.text = dpg.add_input_text(parent=self.child_window, multiline=True, readonly=True, width=-1, height=-1)
        dpg.bind_item_theme(self.text, MultilineText.TEXT_THEME)

        with dpg.item_handler_registry() as self.resize_handler:
            dpg.add_item_resize_handler(callback=self.__on_resize)
        dpg.bind_item_handler_registry(self.text, self.resize_handler)
        
    def add_message(self, message: str, immediate_draw=True):
        if len(self.messages) == self.max_messages:
            del self.modified_messages[0]
            del self.messages[0]
        self.messages.append(message)
        #Hyphens are often negative signs, which is real awkward to break on
        message = textwrap.fill(message, width=self.wrap_chars, break_long_words=True, break_on_hyphens=False)
        self.modified_messages.append(message)
        if immediate_draw:
            self.update()
    
    def update(self, ignore_scroll=False):
        msg = '\n'.join(self.modified_messages)
        dpg.set_item_height(self.text, dpg.get_text_size(msg)[1] + (2 * MultilineText.FRAME_PADDING))
        dpg.set_value(self.text, msg)
        if self.auto_scroll_enabled and not ignore_scroll:
            dpg.set_y_scroll(self.child_window, -1)

    def clear(self):
        self.messages.clear()
        self.modified_messages.clear()
        self.update()

    def is_hovered(self):
        return dpg.is_item_hovered(self.text) or dpg.is_item_hovered(self.child_window)

    def auto_scroll(self, enabled: bool):
        self.auto_scroll_enabled = enabled
        dpg.set_value(self.scroll_checkbox, enabled)

    def __on_resize(self, sender, app_data, user_data):
        new_width = dpg.get_item_rect_size(self.text)[0] - (2 * MultilineText.FRAME_PADDING)
        self.wrap_chars = int(new_width / dpg.get_text_size("O")[0])
        for i, message in enumerate(self.messages):
            self.modified_messages[i] = textwrap.fill(message, width=self.wrap_chars, break_long_words=True, break_on_hyphens=False)

        self.update(ignore_scroll=True)

    def submit(self, parent = None):
        if parent:
            self.window_id = parent
        else:
            self.window_id = dpg.add_window(label="mvLogger", pos=(200, 200), width=500, height=500)
        
        dpg.push_container_stack(self.window_id)
        dpg.unstage(self.stage_id)
        dpg.pop_container_stack() 

    def destroy(self):
        dpg.delete_item(self.resize_handler)
        dpg.delete_item(self.stage_id)

if __name__ == "__main__":
    dpg.create_context()
    dpg.create_viewport()

    logger = MultilineText()
    logger.submit()

    def load_messages():
        print("Loading messages")
        for i in range(50):
            logger.add_message(f"This is line {i}")
        logger.add_message("Hello" * 15)
        logger.add_message("My friend")
        logger.add_message("How are you?")

    with dpg.window() as window:
        dpg.add_button(label="Load", callback=load_messages)

    dpg.set_primary_window(window, True)        

    def wheel_callback(sender, app_data, user_data):
        print(f"{app_data=}")
        hovered = dpg.is_item_hovered(logger.text) or dpg.is_item_hovered(logger.child_window)
        print(f"{hovered=}")        

    with dpg.handler_registry():
        dpg.add_mouse_wheel_handler(callback=wheel_callback)

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_frame_callback(1, load_messages)
    dpg.start_dearpygui()
    dpg.destroy_context()