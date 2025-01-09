import math
import dearpygui.dearpygui as dpg
from dataclasses import dataclass
from contextlib import contextmanager
import yostlabs.tss3.eepts as yleepts

#This is used for fixing a DPG custom series memory leak issue
import ctypes
Py_DECREF = ctypes.pythonapi.Py_DecRef
Py_DECREF.argtypes = (ctypes.py_object,)
Py_DECREF.restype  = None

#http://www.movable-type.co.uk/scripts/latlong.html
def get_distance(start_lat, start_lon, end_lat, end_lon):
    """
    Return the straight line distance between two gps points
    in meters
    """
    R = 6371000
    start_lat_rad = math.radians(start_lat)
    start_lon_rad = math.radians(start_lon)
    end_lat_rad = math.radians(end_lat)
    end_lon_rad = math.radians(end_lon)

    lat_delta = end_lat_rad - start_lat_rad
    lon_delta = end_lon_rad - start_lon_rad

    a = math.sin(lat_delta / 2) ** 2 + math.cos(start_lat_rad) * math.cos(end_lat_rad) * (math.sin(lon_delta / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c    

def get_bearing(start_lat, start_lon, end_lat, end_lon):
    """
    Return the heading in degrees going from start to end
    with a range of 0-360 when given lat and long in degree decimal format
    """
    start_lat_rad = math.radians(start_lat)
    start_lon_rad = math.radians(start_lon)
    end_lat_rad = math.radians(end_lat)
    end_lon_rad = math.radians(end_lon)

    lon_delta = end_lon_rad - start_lon_rad

    y = math.sin(lon_delta) * math.cos(end_lat_rad)
    x = math.cos(start_lat_rad) * math.sin(end_lat_rad) - math.sin(start_lat_rad) * math.cos(end_lat_rad) * math.cos(lon_delta)
    bearing = math.atan2(y, x)
    bearing = (math.degrees(bearing) + 360) % 360
    return bearing

def get_latlon_position(start_lat, start_lon, heading_radians, distance_meters):
    """
    Given a starting GPS position, a heading, and a distance, calculate the new GPS position
    """
    EARTH_RAD_KILOMETERS = 6371
    start_lat_radians = math.radians(start_lat)
    angular_distance = (distance_meters / 1000.0) / EARTH_RAD_KILOMETERS
    lat2_rad = math.asin(math.sin(start_lat_radians) * math.cos(angular_distance) + math.cos(start_lat_radians) * math.sin(angular_distance) * math.cos(heading_radians))

    start_lon_radians = math.radians(start_lon)
    lon_y = math.sin(heading_radians) * math.sin(angular_distance) * math.cos(start_lat_radians)
    lon_x = math.cos(angular_distance) - math.sin(start_lat_radians) * math.sin(lat2_rad)
    lon2_rad = start_lon_radians + math.atan2(lon_y, lon_x)

    lat2_deg = math.degrees(lat2_rad)
    lon2_deg = math.degrees(lon2_rad)
    return lat2_deg, lon2_deg

@dataclass
class GraphPoint:
    """
    General GraphPoint to use when Graphing
    """
    x: float = 0
    y: float = 0

    point_radius: int = 0.3
    point_color: list[float, float, float, float]|None = None

    line_color: list[float, float, float, float]|None = None

    hover_text: str = None

class GpsPoint(GraphPoint):
    """
    Allows converting GPS points to X Y Cartesian Points
    """
    latitude: float
    longitude: float

    def __init__(self, latitude, longitude, previous_point: "GpsPoint" = None):
        self.latitude = latitude
        self.longitude = longitude
        self.calculate_xy(previous_point)

    def calculate_xy(self, previous_point: "GpsPoint"):
        """
        Given a previous GPS point with a valid x and y field,
        calculate this points x and y field relative to that point
        """
        if previous_point is None:
            self.x = 0
            self.y = 0
            return
        distance = get_distance(previous_point.latitude, previous_point.longitude, self.latitude, self.longitude)
        bearing = get_bearing(previous_point.latitude, previous_point.longitude, self.latitude, self.longitude)
        heading = (90 - bearing + 360) % 360 #Convert from GPS angle to cartesian angle
        heading_radians = math.radians(heading)
        self.x = previous_point.x + math.cos(heading_radians) * distance
        self.y = previous_point.y + math.sin(heading_radians) * distance

class PathPoint(GpsPoint):
    """
    A GPS point with additional functionality built into it
    based around EEPTS segments
    """
    SENSOR_COLOR_LINES_DICT: dict[int, tuple[int, int, int, int]] = {
        yleepts.YL_LOCOMOTION_IDLE: (0,255,0,255),  # default / idle
        yleepts.YL_LOCOMOTION_WALKING: (0,255,0,255),  # walk
        yleepts.YL_LOCOMOTION_JOGGING: (255,0,255,255),  # jog
        yleepts.YL_LOCOMOTION_RUNNING: (0,255,255,255),  # run
        yleepts.YL_LOCOMOTION_CRAWLING: (255,255,0,255),  # crawl
        yleepts.YL_LOCOMOTION_UNKNOWN: (0, 0, 0, 255),
        yleepts.YL_LOCOMOTION_OTHER: (255, 255, 255, 255)
    }

    def __init__(self, sinfo: yleepts.Segment, last_sinfo: yleepts.Segment, root_point: GpsPoint = None):
        super().__init__(sinfo.estimated_gps_latitude, sinfo.estimated_gps_longitude, root_point)
        self.sinfo = sinfo
        if last_sinfo is not None and last_sinfo.start_global_index + last_sinfo.len == sinfo.start_global_index:
            self.point_color = [0, 127, 127, 70] #Just a step
        else:
            self.point_color = [0, 255, 0, 70] #This is the first step from idle

        if len(self.sinfo.debug_msgs) != 0: #Mark segments with msgs by making blue fully blue
            self.point_color[2] = 255

        self.line_color = PathPoint.SENSOR_COLOR_LINES_DICT[sinfo.estimated_locomotion_mode]
        self.hover_text = str(sinfo)
        debug_msg_index = self.hover_text.find("debug_msgs:")
        self.hover_text = self.hover_text[:debug_msg_index]
        for debug_msg in self.sinfo.debug_msgs:
            self.hover_text += f"{debug_msg.get_display_str()}\n"

class PathSeries:
    """
    A custom series implementation that allows features such as point hovering for text and
    dynamic coloring. There are a lot of bugs with custom series, but this works around them.
    """
    def __init__(self, graph_points: list[GraphPoint], plot_parent, y_axis = None, label=None, 
                 error: float = None, test_point: GraphPoint = None):
        """
        Parameters:
        graph_points - The points to graph with any desired metadata information filled out
        plot_parent - The plot this is a child of (Where the graph will be drawn)
        y_axis - Does not affect drawing, but is required for what will be considered the custom_series parent
                    Can leave as None is this object is constructed with y_axis at the top of the DPG container stack
        label - How the custom series will be displayed in the Plot Legend

        Planned for removal:
        error - Given a distance in meters, draw a circle with that radius at the end to signify error range
        test_point - The point to compare to the end point to determine path error
        """
        #Controlling how the window auto resizes when clicking
        self.min_x = math.inf
        self.max_x = -math.inf
        self.min_y = math.inf
        self.max_y = -math.inf

        #Controls the Error circle drawing
        self.error = error
        self.draw_error_at_end = True #True if at end, False if at start
        self.test_point = test_point #The point to test against the error point and display distance

        #Actual points to draw
        self.points: list[GraphPoint] = []

        #Setup the Custom Series
        self.plot = plot_parent
        y_axis = y_axis or dpg.top_container_stack()
        with dpg.custom_series([0, 0], [0, 0], channel_count=2, callback=self.callback, tooltip=False, label=label, parent=y_axis) as self.series:
            with dpg.group(show=False) as self.menu_group:
                self.show_checkbox = dpg.add_checkbox(label="Enabled:", default_value=True, show=True, callback=self.__show_checkbox_callback)
            self.hover_text = dpg.add_text("", wrap=600)
        self.parent = dpg.get_item_parent(self.series)
        self.dirty = False #Used to decide when to redraw
        
        #Initialize the Graph with the given points.
        self.set_points(graph_points)
        
        dpg.push_container_stack(self.plot)
        self.draw_layer = dpg.add_draw_layer() #This is where we will draw to to keep stuff organized
        dpg.pop_container_stack()

        self.enabled = True #Tracking whether or not this custom series is enabled seperately from the series itself
        self.search_string = None
        self.search_params = []
        self.negative_search_params = []
        self.radius_scalar = 1

        self.deleted = False

    def __show_checkbox_callback(self, sender, app_data):
        if app_data:
            self.show()
        else:
            self.hide()

    def set_search_string(self, search: str):
        """
        Parse the search string and update the graph to show only points that match the search string
        """
        self.search_string = search.casefold()

        self.search_params = []
        self.negative_search_params = []
        param = ""
        allow_spaces = False
        for char in self.search_string:
            if char == ' ' and not allow_spaces:
                if param[0] == '!':
                    self.negative_search_params.append(param[1:])
                else:
                    self.search_params.append(param)
                param = ""
            elif char == '"':
                allow_spaces = not allow_spaces
            else:
                param += char
        if param:
            if param[0] == '!':
                self.negative_search_params.append(param[1:])
            else:
                self.search_params.append(param)
        self.set_dirty()

    def compare_search_string(self, string: str):
        """
        Compares string against the currently set search filter
        Returns:
        True if matches the filter (Should be Shown), else False
        """
        string = string.casefold()
        if any(param not in string for param in self.search_params) or any(param in string for param in self.negative_search_params):
            return False
        return True

    def set_radius_scalar(self, scalar: str):
        """
        Update the radius scalar to make the points display bigger
        """
        self.radius_scalar = scalar
        self.set_dirty()

    def add_point(self, point: GraphPoint):
        """
        Add a point to the graph to be shown
        """
        self.points.append(point)
        self.dirty = True

        self.min_x = min(self.min_x, point.x)
        self.max_x = max(self.max_x, point.x)
        self.min_y = min(self.min_y, point.y)
        self.max_y = max(self.max_y, point.y)

        dpg.configure_item(self.series, x = [self.min_x, self.max_x], y = [self.min_y, self.max_y])
    
    def set_points(self, graph_points: list[GraphPoint]):
        self.clear()
        for point in graph_points:
            self.add_point(point)

    def clear(self):
        self.min_x = math.inf
        self.max_x = -math.inf
        self.min_y = math.inf
        self.max_x = -math.inf
        dpg.configure_item(self.series, x = [0,0], y = [0,0])
        self.points.clear()
        self.set_dirty()

    def set_dirty(self):
        self.dirty = True

    def hide(self):
        if not self.enabled:
            return
        self.enabled = False
        self.set_dirty()

    def show(self):
        if self.enabled:
            return
        self.enabled = True
        self.set_dirty()

    def callback(self, sender, app_data):
        #Its possible when using manual callbacks that the callback gets scheduled and then the series is deleted
        #This prevents modifying a deleted series when that occurs
        if self.deleted: 
            Py_DECREF(app_data) #Memory leak fix
            return
        _helper_data = app_data[0]
        mouse_x_plot_space = _helper_data["MouseX_PlotSpace"] #Plot Space = Coordinate in the Graph
        mouse_y_plot_space = _helper_data["MouseY_PlotSpace"]
        mouse_x_pixel_space = _helper_data["MouseX_PixelSpace"] #Pixel Space = Coordinate in the Viewport
        mouse_y_pixel_space = _helper_data["MouseY_PixelSpace"]

        #Interactive Elements!
        if self.enabled:
            tooltip_enabled = False
            for point in self.points:
                if not point.point_radius or not point.hover_text:
                    continue
                mouse_dist_squared = ((mouse_x_plot_space - point.x) ** 2 + (mouse_y_plot_space - point.y) ** 2)

                if mouse_dist_squared < (point.point_radius * self.radius_scalar) ** 2:
                    valid_search = self.compare_search_string(point.hover_text)
                    if valid_search:
                        dpg.set_value(self.hover_text, point.hover_text)
                        tooltip_enabled = True
                        break
            dpg.configure_item(self.series, tooltip=tooltip_enabled)
            dpg.configure_item(self.hover_text, show=tooltip_enabled)
            dpg.configure_item(self.menu_group, show=not tooltip_enabled) #Only show if no tooltip

        if not self.dirty:
            Py_DECREF(app_data) #Memory leak fix
            return

        #Draw to the plot this belongs to
        #We don't use transformed_x/y cause its in pixel space, and would require redrawing every zoom, which is awful
        #Drawing directly to the plot instead, while requires more overhead from ourselves, is WAY more efficient
        #Clear out old
        dpg.delete_item(self.draw_layer, children_only=True)
        
        if self.enabled:
            num_points = len(self.points)
            #Draw Lines first
            dpg.push_container_stack(self.draw_layer)
            for i in range(1, num_points):
                point = self.points[i]
                prev_point = self.points[i-1]
                line_color = point.line_color or (255, 255, 0, 255)
                line = dpg.draw_line((prev_point.x, prev_point.y), (point.x, point.y), color=line_color, thickness=0)
            #Draw Circles second so they are on top
            for i in range(num_points):
                point = self.points[i]
                valid_search = self.compare_search_string(point.hover_text)
                if point.point_radius > 0 and valid_search:
                    color = point.point_color or (255, 0, 0, 255)
                    circle = dpg.draw_circle(center=(point.x, point.y), radius=point.point_radius * self.radius_scalar, color=color, fill=color)
            
            dpg.pop_container_stack()

        self.dirty = False
        Py_DECREF(app_data) #Memory leak fix

    @contextmanager
    def menu(self):
        """
        Used to allow someone to modify the legend menu for this series
        """
        dpg.push_container_stack(self.menu_group)
        yield
        dpg.pop_container_stack()

    def delete(self):
        self.deleted = True #Done to manage manual callbacks potentially calling the custom series callback after deletion
        dpg.delete_item(self.draw_layer)
        dpg.delete_item(self.series)
