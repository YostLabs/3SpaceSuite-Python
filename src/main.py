if __name__ == "__main__":

    import platform
    import asyncio
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    import sys
    import bleak.backends.winrt.util as bleak_util
    bleak_util.allow_sta() #Using a GUI that handles the event loop without a background thread for asyncio, so allow_sta
    print("Starting main")
    from managers.resource_manager import *
    import dearpygui.dearpygui as dpg
    from graphics.gl_renderer import GL_Renderer
    from gui.main_menubar import MenuBar
    import gui.resources.theme_lib as theme_lib, gui.resources.obj_lib as obj_lib, gui.resources.texture_lib as texture_lib
    import time

    #Initialization
    dpg.create_context()
    dpg.create_viewport()

    dpg.create_viewport(title=APPNAME, large_icon=(IMAGE_FOLDER / "icon.ico").as_posix(), height=815)

    theme_lib.init()
    texture_lib.init()

    from third_party.file_dialog.fdialog import FileDialog
    image_root = RESOURCE_FOLDER / "images" / "fdialog"
    print(f"{image_root=}")
    FileDialog.set_image_root(image_root.as_posix() + "/")

    from utility import Logger, MainLoopEventQueue
    Logger.init()
    from gui.core_ui import FontManager
    GL_Renderer.init()
    obj_lib.init()

    FontManager.init()
    dpg.bind_font(FontManager.DEFAULT_FONT)
    GL_Renderer.set_font((FONT_FOLDER / "FiraCode-Regular.ttf").as_posix(), 48)

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
                    from gui.core_ui import BannerMenu
                    banner_menu = BannerMenu()
                    banner_menu.submit()
                with dpg.table_cell(label="Viewport Cell"):
                    from gui.core_ui import DynamicViewport
                    selected_viewport = DynamicViewport() #Just reserving space
                    selected_viewport.submit()


    from managers.general_managers import GeneralManager
    general_manager = GeneralManager(banner_menu, selected_viewport)
    menu = MenuBar(menu_bar, general_manager)

    general_manager.load_main_window()

    dpg.set_primary_window(primary_window, True)

    dpg.set_viewport_min_height(550)
    dpg.set_viewport_min_width(586)

    #Start DearPyGUI and show
    dpg.setup_dearpygui()
    dpg.set_viewport_vsync(False)
    dpg.show_viewport()

    #TEMPORARY - The bleak_util.allow_sta() should be all that is needed, however
    #that appears to not fully work on Windows 11, Windows 10 it does. This does fix problems
    #encountered on Windows11, however I do not know what side effects this may have since this
    #is an actual GUI program that wants to use STA. This is being put in for now as a quick fix
    if platform.system() == 'Windows' and int(platform.version().split('.')[2]) >= 22000: #Can't user platform.release() to check for 11 because windows 11 still returns 10...
        bleak_util.uninitialize_sta()

    #Done to allow the UI to initialize before discovering devices, that way if any logging messages
    #or errors are thrown, the app won't crash as it tries to modify and uninitialized UI
    dpg.configure_app(manual_callback_management=True)
    dpg.set_frame_callback(2, general_manager.device_manager.discover_devices)
    last_update_time = time.time()
    MAX_FPS = 120

    #Try except is for if application is not ran with PyInstaller bootloader
    try:
        import pyi_splash
        pyi_splash.close()
    except: pass

    #The purpose of this is to be a function that runs once per frame from DPGs handler thread
    #The reason for its existence is https://github.com/hoffstadt/DearPyGui/issues/2366
    #Basically, any DPG call has the potential to deadlock the program if not called from the DPG
    #handler thread. This provides a way for the main thread to schedule DPG calls that will be executed
    #from that thread
    def on_visible(unused):
        MainLoopEventQueue.process_dpg_events()

    with dpg.item_handler_registry() as visible_handler:
        dpg.add_item_visible_handler(callback=on_visible)
    dpg.bind_item_handler_registry(primary_window, visible_handler)

    last_render_time = time.perf_counter()
    while dpg.is_dearpygui_running():
        start_time = time.time()
        general_manager.device_manager.update()
        end_time = time.time()
        elapsed_time = end_time - start_time
        if elapsed_time > 0.1:
            print("Long update time:", elapsed_time)
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
        MainLoopEventQueue.process_sync_events()
        dpg.run_callbacks(jobs) #I am not actually sure this is safe anymore because of the issue related to the visible_handler

        cur_time = time.perf_counter()
        if cur_time - last_render_time > 1 / MAX_FPS:
            dpg.render_dearpygui_frame()
            last_render_time = cur_time

    #Cleanup anything needed before shutting down
    general_manager.cleanup()
    menu.cleanup()
    Logger.cleanup()

    #Shut down
    dpg.destroy_context()
    GL_Renderer.cleanup()