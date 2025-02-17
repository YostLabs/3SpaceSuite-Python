print("Starting main")
from resource_manager import *
import dearpygui.dearpygui as dpg
from gl_renderer import GL_Renderer
from main_menubar import MenuBar
import theme_lib, obj_lib
import time

#Initialization
dpg.create_context()
dpg.create_viewport()

dpg.create_viewport(title="YL 3-Space Suite", large_icon=(IMAGE_FOLDER / "icon.ico").as_posix(), height=815)

theme_lib.init()

from utility import Logger, MainLoopEventQueue
Logger.init()
from core_ui import FontManager
GL_Renderer.init()
obj_lib.init()
FontManager.init()
dpg.bind_font(FontManager.DEFAULT_FONT)
GL_Renderer.set_font((FONT_FOLDER / "comic.ttf").as_posix(), 48)

#Create Window Structures and connections
with dpg.window(label="Main Window") as primary_window:
    with dpg.menu_bar() as menu_bar:
        pass
    
    with dpg.table(header_row=False, label="Grid", resizable=True, scrollY=True, 
                   borders_outerH=False, borders_innerH=False, borders_innerV=False, borders_outerV=False):
        dpg.add_table_column(width_stretch=True, init_width_or_weight=200, label="MainMenuCol")
        dpg.add_table_column(width_stretch=True, init_width_or_weight=800, label="SelectedViewCol")
        with dpg.table_row(label="Table Row"):
            with dpg.table_cell(label="Banner Menu Cell"):
                from core_ui import BannerMenu
                banner_menu = BannerMenu()
                banner_menu.submit()
            with dpg.table_cell(label="Viewport Cell"):
                from core_ui import DynamicViewport
                selected_viewport = DynamicViewport() #Just reserving space
                selected_viewport.submit()


from general_managers import GeneralManager
general_manager = GeneralManager(banner_menu, selected_viewport)
menu = MenuBar(menu_bar, general_manager)

general_manager.load_main_window()

dpg.set_primary_window(primary_window, True)

dpg.set_viewport_min_height(550)
dpg.set_viewport_min_width(586)

#Start DearPyGUI and show
dpg.setup_dearpygui()
dpg.set_viewport_vsync(False) #No real benefit to this being false except more time will be spent in the render thread
dpg.show_viewport()

#Done to allow the UI to initialize before discovering devices, that way if any logging messages
#or errors are thrown, the app won't crash as it tries to modify and uninitialized UI
dpg.configure_app(manual_callback_management=True)
dpg.set_frame_callback(2, general_manager.device_manager.discover_devices)
#dpg.start_dearpygui()
last_update_time = time.time()

#Try except is for if application is not ran with PyInstaller bootloader
try:
    import pyi_splash
    pyi_splash.close()
except: pass

while dpg.is_dearpygui_running():
    general_manager.device_manager.update()
    general_manager.logger_manager.update()
    
    #To avoid threading issues, running callbacks here
    #This is supposedly slower, but I don't feel like wrapping
    #every single threespace API call into a lock right now
    jobs = dpg.get_callback_queue()

    #Do this after the jobs in case any jobs schedule events
    #This is to compensate for the fact not all callbacks are properly handled via manual_callback.
    #Callbacks that are not done manually and need to use this system:
    #set_exit_callback
    #add_drag_ZZZ
    #callback on table
    #on_close on dpg.window
    #cancel_callback on file_dialog
    #all global/item handler callbacks via dpg.handler_registry/dpg.item_handler_registry
    #https://github.com/hoffstadt/DearPyGui/issues/2208
    MainLoopEventQueue.process_queued_events()
    dpg.run_callbacks(jobs)
    # if time.time() - last_update_time > 1/100: #Not doing any smart logic, just limiting the time in the render. This will prob get like 75 FPS
    #     dpg.render_dearpygui_frame()
    #     last_update_time = time.time()
    dpg.render_dearpygui_frame()

#Cleanup anything needed before shutting down
general_manager.cleanup()
menu.cleanup()
Logger.cleanup()

#Shut down
dpg.destroy_context()
GL_Renderer.cleanup()