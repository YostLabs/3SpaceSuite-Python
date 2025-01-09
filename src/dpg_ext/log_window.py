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