import dearpygui.dearpygui as dpg
from fdialog import FileDialog

import pathlib

image_folder = pathlib.Path(__file__).parent.parent.parent.parent / "resources" / "images" / "fdialog"
print(image_folder)
FileDialog.set_image_root(image_folder.as_posix() + "/")

dpg.create_context()

def pr(selected_files): # file_dialog calls the callback with as argument a list containing the selected files
    dpg.delete_item("txt_child", children_only=True)
    for file in selected_files:
        dpg.add_text(file, parent="txt_child")

def on_cancel():
    print("Canceled selection")



dpg.create_viewport(title='file_dialog example')
dpg.set_viewport_vsync(False)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.render_dearpygui_frame()

fd = FileDialog(on_select=pr, on_cancel=on_cancel, default_path="..", multi_selection=True, files_only=True, dirs_only=False, no_resize=False)
with dpg.window(label="hi", height=480, width=600):
    dpg.add_button(label="Show file dialog", callback=fd.show_file_dialog)
    dpg.add_child_window(width=-1, height=-1, tag="txt_child")
dpg.start_dearpygui()
dpg.destroy_context()