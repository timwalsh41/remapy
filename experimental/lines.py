import os
import struct
import json
import re
import enum
import numpy as np

from reportlab.lib import colors

# file header is different for v3/v5
expected_header_v3 = b'reMarkable .lines file, version=3          '
expected_header_v5 = b'reMarkable .lines file, version=5          '

# Remarkable constants
REMARKABLE_DISPLAY_MAX_X = 1404
REMARKABLE_DISPLAY_MAX_Y = 1872


def matrix_to_line(matrix, offset_x = 0, offset_y = 0, x_scale=1, y_scale=1):
    if not isinstance(matrix, np.ndarray):
        print('Error: matrix must be a two dimensional numpy ndarray')
        return

    if not len(matrix.shape) == 2:
        print('Error: matrix must be a two dimensional numpy ndarray')
        return

    new_line = Line(pen_nr = Pen.BALLPOINT, color=0, i_unk=0, width=0.5)

    points = [Point(x=j*x_scale+offset_x,y=-i*y_scale+offset_y,tilt=0,speed=1,pressure=matrix[i,j]/255,width=0.5)
              for i in range(matrix.shape[0]) for j in range(matrix.shape[1]) if matrix[i,j] > 100]

    for point in points:
        new_line.add_point(point)

    return new_line


# pen types
class Pen(enum.Enum):
    HIGHLIGHTER = 1
    ERASER = 2
    ERASER_AREA = 3
    SHARP_PENCIL = 4
    TILT_PENCIL = 5
    MARKER = 6
    BALLPOINT = 7
    FINELINER = 8
    BRUSH = 9
    CALLIGRAPHY = 10
    UNKNOWN = 11


class Point:
    def __init__(self, x = None, y = None, speed = None, tilt = None, width = None, pressure = None):
        self.x = x
        self.y = y
        self.speed = speed
        self.tilt = tilt
        self.width = width
        self.pressure = pressure


class Line:
    def __init__(self, pen_nr = None, color = None, i_unk = None, width = None):
        self._pen_nr = pen_nr
        self._color = color
        self._i_unk = i_unk
        self._width = width

        self._point_count = 0
        self._points = []


    def set_pen(self, new_pen):
        if not isinstance(new_pen, Pen):
            print('Error - set_pen requires a valid Pen')
            return

        self._pen_nr = new_pen

    def add_point(self, new_point = None):
        if not isinstance(new_point, Point):
            print('Error - add_point requires a valid Point')
            return

        self._points.append(new_point)
        self._point_count += 1


    def get_points(self):
        return self._points


    def get_pen_nr_code(self):
        if self._pen_nr == Pen.HIGHLIGHTER:
            return 5
        elif self._pen_nr == Pen.ERASER:
            return 6
        elif self._pen_nr == Pen.ERASER_AREA:
            return 8
        elif self._pen_nr == Pen.SHARP_PENCIL:
            return 7
        elif self._pen_nr == Pen.TILT_PENCIL:
            return 1
        elif self._pen_nr == Pen.MARKER:
            return 3
        elif self._pen_nr == Pen.BALLPOINT:
            return 2
        elif self._pen_nr == Pen.FINELINER:
            return 4
        elif self._pen_nr == Pen.BRUSH:
            return 0
        elif self._pen_nr == Pen.CALLIGRAPHY:
            return 21
        else:
            return 0


    def get_color(self):
        return self._color


    def get_i_unk(self):
        return self._i_unk


    def get_width(self):
        return self._width


    def get_point_count(self):
        return self._point_count

    def get_point_coordinates_as_list(self):
        x = []
        y = []

        for point in self._points:
            x.append(point.x)
            y.append(point.y)

        return x,y


class Layer:
    def __init__(self):
        self._line_count = 0
        self._lines = []

    def add_line(self, new_line):
        if not isinstance(new_line, Line):
            print('Error: add_line requires a valid Line')
            return

        self._lines.append(new_line)
        self._line_count += 1


    def get_lines(self):
        return self._lines


class Page:
    def __init__(self):
        self._is_v3 = False
        self._is_v5 = False

        self._layer_count = 0
        self._layers = []


    def add_layer(self, new_layer):
        if not isinstance(new_layer, Layer):
            print('Error: add_layer requires a valid Layer')
            return

        self._layers.append(new_layer)
        self._layer_count += 1


    def get_layers(self):
        return self._layers


    def write_output_file(self, output_file_path):

        with open(output_file_path, 'wb') as f:
            fmt = '<{}sI'.format(len(expected_header_v5))
            b = struct.pack(fmt, expected_header_v5, self._layer_count)
            f.write(b)

            for layer in self.get_layers():
                fmt = '<I'
                b = struct.pack(fmt, len(layer.get_lines()))
                f.write(b)

                for line in layer.get_lines():
                    fmt = '<IIIffI'
                    b = struct.pack(fmt, line.get_pen_nr_code(), line.get_color(),
                                    line.get_i_unk(), line.get_width(), 0, line.get_point_count())
                    f.write(b)

                    for point in line.get_points():
                        fmt = '<ffffff'
                        b = struct.pack(fmt, point.x, point.y, point.speed, point.tilt, point.width, point.pressure)
                        f.write(b)

        return 0


class LineParser:
    def __init__(self, rm_file_path = None):
        self._rm_file_path = rm_file_path
        self._rm_file_binary_data = None


    def set_file_path(self, rm_file_path):
        self._rm_file_path = rm_file_path
        self._rm_file_binary_data = None


    def read_rm_file(self, rm_file_path = None):
        if rm_file_path is not None:
            self._rm_file_path = rm_file_path

        if not os.path.exists(self._rm_file_path):
            print('Error - invalid rm file path: {}'.format(self._rm_file_path))
            return

        with open(self._rm_file_path, 'rb') as f:
            self._rm_file_binary_data = f.read()


    def parse_rm_data(self):
        # extract metadate file path
        metadata_file_path = self._rm_file_path[:-3] + '-metadata.json'

        if self._rm_file_binary_data is None:
            print('Error - must read in RM file first')
            return

        # offset will track our position in the binary data file as we parse through
        # each section
        offset = 0

        if len(self._rm_file_binary_data) < len(expected_header_v5) + 4:
            print('File too short to be a valid file')
            return

        this_page = Page()

        # read out the header string and number of layers
        fmt = '<{}sI'.format(len(expected_header_v5))
        header, nlayers = struct.unpack_from(fmt, self._rm_file_binary_data, offset)

        # increment the offset for the header we just read
        offset += struct.calcsize(fmt)

        # verify we have a valid v3 or v5 file
        this_page._is_v3 = (header == expected_header_v3)
        this_page._is_v5 = (header == expected_header_v5)
        if (not this_page._is_v3 and not this_page._is_v5) or nlayers < 1:
            print('Not a valid reMarkable file: <header={}><nlayers={}>'.format(header, nlayers))
            return

        # Load name of layers; if layer name starts with # we use this color
        # for this layer
        layer_colors = [None for _ in range(nlayers)]
        if os.path.exists(metadata_file_path):
            with open(metadata_file_path, "r") as meta_file:
                layers = json.loads(meta_file.read())["layers"]

            for l in range(len(layers)):
                layer = layers[l]

                matches = re.search(r"#([^\s]+)", layer["name"], re.M | re.I)
                if not matches:
                    continue
                color_code = matches[0].lower()

                # Try to parse hex code
                try:
                    has_alpha = len(color_code) > 7
                    layer_colors[l] = colors.HexColor(color_code, hasAlpha=has_alpha)
                    continue
                except:
                    pass

        # parse each layer
        for layer in range(nlayers):
            this_layer = Layer()

            # read out number of strokes in current layer
            fmt = '<I'
            (this_layer._line_count,) = struct.unpack_from(fmt, self._rm_file_binary_data, offset)
            offset += struct.calcsize(fmt)

            # Iterate through the strokes in the layer (If there is any)
            for stroke in range(this_layer._line_count):
                if this_page._is_v3:
                    fmt = '<IIIfI'
                    pen_nr, color, i_unk, width, segments_count = struct.unpack_from(fmt, self._rm_file_binary_data, offset)
                    offset += struct.calcsize(fmt)
                if this_page._is_v5:
                    fmt = '<IIIffI'
                    pen_nr, color, i_unk, width, unknown, segments_count = struct.unpack_from(fmt, self._rm_file_binary_data, offset)
                    offset += struct.calcsize(fmt)

                last_width = 0

                this_line = Line(None, color, i_unk, width)

                # Check which tool is used for both, v3 and v5 and set props
                # https://support.remarkable.com/hc/en-us/articles/115004558545-5-1-Tools-Overview
                if pen_nr == 5 or pen_nr == 18:
                    this_line.set_pen(Pen.HIGHLIGHTER)
                elif pen_nr == 6:
                    this_line.set_pen(Pen.ERASER)
                elif pen_nr == 8:
                    this_line.set_pen(Pen.ERASER_AREA)
                elif pen_nr == 7 or pen_nr == 13:
                    this_line.set_pen(Pen.SHARP_PENCIL)
                elif pen_nr == 1 or pen_nr == 14:
                    this_line.set_pen(Pen.TILT_PENCIL)
                elif pen_nr == 3 or pen_nr == 16:
                    this_line.set_pen(Pen.MARKER)
                elif pen_nr == 2 or pen_nr == 15:
                    this_line.set_pen(Pen.BALLPOINT)
                elif pen_nr == 4 or pen_nr == 17:
                    this_line.set_pen(Pen.FINELINER)
                elif pen_nr == 0 or pen_nr == 12:
                    this_line.set_pen(Pen.BRUSH)
                elif pen_nr == 21:
                    this_line.set_pen(Pen.CALLIGRAPHY)
                else:
                    this_line.set_pen(Pen.UNKNOWN)

                # Now capture the points
                for segment in range(segments_count):
                    fmt = '<ffffff'
                    x, y, speed, tilt, width, pressure = struct.unpack_from(fmt, self._rm_file_binary_data, offset)
                    offset += struct.calcsize(fmt)

                    this_point = Point(x, y, speed, tilt, width, pressure)

                    this_line.add_point(this_point)

                this_layer.add_line(this_line)

            this_page.add_layer(this_layer)

        return this_page
