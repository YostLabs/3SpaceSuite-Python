import dearpygui.dearpygui as dpg

color_x = (255, 0, 0)
color_y = (0, 230, 0)
color_z = (96, 125, 229)
#color_z = (0, 102, 204) #More blue
#color_w = (255, 191, 0) #More yellow then orange
color_w = (255, 128, 0)

color_white = (255, 255, 255)
color_green = (0, 255, 0)

color_tooltip = (0, 0xBF, 0xFF)

color_disconnect_red = (178, 34, 34) #Firebrick Red

plot_x_line_theme = None
plot_y_line_theme = None
plot_z_line_theme = None
plot_w_line_theme = None

plot_indicator_theme = None

connect_button_theme = None

hyperlink_theme = None

red_button_theme = None

def init():
    global plot_x_line_theme, plot_y_line_theme, plot_z_line_theme, plot_w_line_theme, plot_indicator_theme, connect_button_theme, hyperlink_theme, red_button_theme

    with dpg.theme(label="plot_x_line_theme") as plot_x_line_theme:
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvPlotCol_Line, color_x, category=dpg.mvThemeCat_Plots) 

    with dpg.theme(label="plot_y_line_theme") as plot_y_line_theme:
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvPlotCol_Line, color_y, category=dpg.mvThemeCat_Plots) 
    
    with dpg.theme(label="plot_z_line_theme") as plot_z_line_theme:
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvPlotCol_Line, color_z, category=dpg.mvThemeCat_Plots) 

    with dpg.theme(label="plot_w_line_theme") as plot_w_line_theme:
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvPlotCol_Line, color_w, category=dpg.mvThemeCat_Plots) 

    with dpg.theme(label="plot_indicator_theme") as plot_indicator_theme:
        with dpg.theme_component(dpg.mvInfLineSeries):
            dpg.add_theme_color(dpg.mvPlotCol_Line, color_white, category=dpg.mvThemeCat_Plots)  

    with dpg.theme(label="connect_button_theme") as connect_button_theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (127, 255, 0, 200))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (127, 255, 0, 160))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (127, 255, 0, 180))

    with dpg.theme(label="red_button_theme") as red_button_theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (*color_disconnect_red, 200))   
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (*color_disconnect_red, 160))   
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (*color_disconnect_red, 180))            
        