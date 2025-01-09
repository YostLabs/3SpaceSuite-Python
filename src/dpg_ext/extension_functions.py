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

def create_confirm_popup(text: str = "", on_cancel: Callable = None, on_confirm: Callable = None, title: str = "Confirmation", width=350,
                            always_center: bool = True):
    """
    Creates a modal window with supplied text and a cancel and confirm button with settable callbacks
    """
    with dpg.window(label=title, modal=True, no_resize=True, show=True, width=width, no_move=always_center) as confirm_popup:
        dpg.add_text(text, wrap=width)
        with dpg.group(horizontal=True):
            confirm_button = dpg.add_button(label="Confirm", user_data=on_confirm)
            cancel_button = dpg.add_button(label="Cancel", user_data=on_cancel)

        visible_handler = None
        if always_center:
            with dpg.item_handler_registry() as visible_handler:
                dpg.add_item_visible_handler(callback=center_window_handler_callback, user_data=confirm_popup)
            dpg.bind_item_handler_registry(confirm_popup, visible_handler)
    
    #Create the popups selection handler
    def __on_selection(sender, app_data, user_data):
        callback = user_data

        #Cleanup
        if visible_handler is not None:
            dpg.delete_item(visible_handler)
        dpg.delete_item(confirm_popup)

        #Callback
        if callback is not None:
            callback()
    
    #Bind the selection handler
    dpg.set_item_callback(confirm_button, __on_selection)
    dpg.set_item_callback(cancel_button, __on_selection)
