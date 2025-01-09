import dearpygui.dearpygui as dpg
from dpg_ext.staged_view import StagedView

class SelectableButton(StagedView):
    """
    A button that can be selected.
    Has an on_select(caller) callback where
    caller is the SelectableButton
    """

    def __init__(self, text = None, selected = False, on_select = None):
        with dpg.theme(label="SelectableButtonSelectedTheme") as self.selected_theme:
            with dpg.theme_component(dpg.mvButton) as self.selected_component:
                dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 119, 200, 153))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 119, 200, 153))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (0, 119, 200, 153))
                self.text_color_selected = None #dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))
        
        with dpg.theme(label="SelectableButtonUnselectedTheme") as self.unselected_theme:
            with dpg.theme_component(dpg.mvButton) as self.unselected_component:
                self.text_color_unselected = None# dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))

        with dpg.stage(label=text or "SelectableButton") as self._stage_id:
            self.button = dpg.add_button(label=text, width=-1, height=50, callback=self.set_selected)
        dpg.bind_item_theme(self.button, self.unselected_theme)
        self.selected = selected
        self.on_select_callbacks = []
        if isinstance(on_select, list):
            self.on_select_callbacks.extend(on_select)
        elif on_select is not None:
            self.on_select_callbacks.append(on_select)
        
        self.color_theme = None

    def set_selected(self):
        if self.selected: #Already selected
            return
        
        dpg.bind_item_theme(self.button, self.selected_theme)
        self.selected = True
        for cb in self.on_select_callbacks:
            cb(self)
    
    def set_unselected(self):
        if not self.selected: #Already not selected
            return
        
        dpg.bind_item_theme(self.button, self.unselected_theme)
        self.selected = False

    def add_selected_callback(self, cb):
        self.on_select_callbacks.append(cb)
    
    def remove_selected_callback(self, cb):
        self.on_select_callbacks.remove(cb)

    def set_text_color(self, color):
        #Setting no color = Delete the color theme
        if color is None:
            if self.text_color_selected == None:
                return
            dpg.delete_item(self.text_color_selected)
            dpg.delete_item(self.text_color_unselected)
            self.text_color_selected = None
            self.text_color_unselected = None
            return

        #Setting a color while it is default = Create theme
        if self.text_color_selected == None:
            dpg.push_container_stack(self.selected_component)
            self.text_color_selected = dpg.add_theme_color(dpg.mvThemeCol_Text, color)
            dpg.pop_container_stack()
            dpg.push_container_stack(self.unselected_component)
            self.text_color_unselected = dpg.add_theme_color(dpg.mvThemeCol_Text, color)
            dpg.pop_container_stack()
        else: #Setting a color while not default = Change color of theme
            dpg.set_value(self.text_color_selected, color)
            dpg.set_value(self.text_color_unselected, color)

    def delete(self):
        for child in dpg.get_item_children(self._stage_id, 1):
            dpg.delete_item(child)
        dpg.delete_item(self.selected_theme)
        dpg.delete_item(self.unselected_theme)
        super().delete()
        # dpg.delete_item(self.button)