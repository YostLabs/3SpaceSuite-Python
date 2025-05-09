import dearpygui.dearpygui as dpg
from typing import Callable

__ITEM_TYPES = None
def get_item_type_value(item):
    """
    Why dpg.get_item_type returns a string, and a string
    that isn't even formatted correctly for the dictionary look
    up in dpg.get_item_types() idk, but this fixes that
    """
    global __ITEM_TYPES
    if __ITEM_TYPES is None:
        __ITEM_TYPES = dpg.get_item_types()
    itype: str = dpg.get_item_type(item)
    itype = itype.split('::')[1]
    return __ITEM_TYPES[itype]

def get_global_item_pos(id):
    pos = dpg.get_item_pos(id)
    parent = dpg.get_item_parent(id)
    if parent is not None:
        parent_pos = get_global_parent_pos(parent)
        pos[0] += parent_pos[0]
        pos[1] += parent_pos[1]
    return pos

def get_global_parent_pos(parent):
    """
    An items type is relative to its parent, so once its
    position is known, you have to recursively get your parents position
    add it to yours. However, some containers, such as groups, do NOT
    do positioning relative to the group, but rather its parents.
    This function handles only adding in the positions of types that matter
    from a parenting perspective and is why it must be seperate from get_global_item_pos
    """
    pos = [0, 0]
    parent_type = get_item_type_value(parent)
    if parent_type not in (dpg.mvGroup, dpg.mvTreeNode, dpg.mvCollapsingHeader): #These don't affect positioning for some reason
        pos = dpg.get_item_pos(parent)
    if parent_type in (dpg.mvTable, dpg.mvChildWindow, dpg.mvWindowAppItem): #These have scrolling that can affect positioning
        pos[0] -= dpg.get_x_scroll(parent)
        pos[1] -= dpg.get_y_scroll(parent)
    parents_parent = dpg.get_item_parent(parent)
    if parents_parent is not None:
        parent_pos = get_global_parent_pos(parents_parent)
        pos[0] += parent_pos[0]
        pos[1] += parent_pos[1]
    return pos

def get_global_rect(item)  -> tuple[int, int, int, int, bool]:
    global_pos = get_global_item_pos(item)
    d  = dpg.get_item_state(item)
    if 'visible' in d:
        return *d['rect_size'], *global_pos, d['visible']  # type: ignore
    return *d['rect_size'], *global_pos, dpg.get_item_configuration(item)['show']  # type: ignore

def center_window_handler_callback(sender, app_data, user_data):
    """
    Use this as a callback to a visible handler, and set the user_data to the window to be centered.
    Then bind that handler to the window and now that window will always be centered
    """
    window = user_data
    if not dpg.does_item_exist(window): return
    center_window(window)

def center_window(window):
    """
    Centers the given window in the viewport
    Warning: If this is the frame the window just became visible, the get_item_rect_size my return incorrect results.
    In that situation, the user should first call render_dearpygui_frame before calling this function
    """
    width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
    mid_x = width // 2
    mid_y = height // 2
    width, height = dpg.get_item_rect_size(window)
    mid_x -= width // 2
    mid_y -= height // 2
    dpg.set_item_pos(window, [mid_x, mid_y])

import webbrowser
hyperlink_theme = None
def add_hyperlink(text: str, address: str):
    global hyperlink_theme
    if hyperlink_theme is None:
        with dpg.theme(label="hyperlink_theme") as hyperlink_theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, [0, 0, 0, 0])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, [0, 0, 0, 0])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, [29, 151, 236, 25])
                dpg.add_theme_color(dpg.mvThemeCol_Text, [29, 151, 236])  
    dpg.add_button(label=text, callback=lambda:webbrowser.open(address))
    dpg.bind_item_theme(dpg.last_item(), hyperlink_theme)
    
from dpg_ext.popup_windows import PopupWindow, PopupButton

def create_popup_circle_loading_indicator(text: str = "", title: str = "", width=350, always_center: bool = True):
    """
    Creates a window with a loading indicator in it, returns a function to call to cleanup the window when done.
    """
    popup = PopupWindow(title=title, width=width, always_center=always_center, no_close=True)
    if text:
        popup.add_text(text)
    popup.add_loading_wheel()
    return popup

def create_popup_message(text: str = "", title: str = "", width=350, always_center: bool = True):
    popup = PopupWindow(title=title, width=width, always_center=always_center).add_text(text)
    popup.add_buttons([PopupButton("Ok", callback=popup.delete)])
    return popup

def create_confirm_popup(text: str = "", on_cancel: Callable = None, on_confirm: Callable = None, title: str = "Confirmation", width=350,
                            always_center: bool = True):
    """
    Creates a modal window with supplied text and a cancel and confirm button with settable callbacks
    """
    return PopupWindow(width=width, always_center=always_center).set_confirm_box(text=text, title=title, on_cancel=on_cancel, on_confirm=on_confirm)