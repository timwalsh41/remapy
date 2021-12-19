import os
import struct
import json
import re
import enum
import numpy as np
import hashlib
import copy

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


# merge two page objects - return a page object that
# represents the combination of all layers & lines in
# both pages
def merge_pages(page_1, md5_1, page_2, md5_2):
    # handle case that one or both page objects is empty
    if len(page_1.get_layers()) == 0:
        if len(page_2.get_layers()) == 0:
            print('Error merging pages - neither page has any layers')
        else:
            return copy.deepcopy(page_2)
    elif len(page_2.get_layers()) == 0:
        return copy.deepcopy(page_1)

    # start the merged page as a copy of page 1
    # then we will loop over layers/lines in page 2 and copy in any for which we don't find a match
    merged_page = copy.deepcopy(page_1)

    # loop over the layers in page 2
    for layer_idx,layer in enumerate(page_2.get_layers()):
        if len(page_1.get_layers()) < (layer_idx + 1):
            # copy current layer from page 2 directly into merged page
            merged_page.add_layer(page_2.get_layers()[layer_idx])

            # continue on to next layer
            continue

        # loop over lines in current layer of page 2
        for line_idx,line in enumerate(layer.get_lines()):
            # get hash of page 2 current line format & data
            page2_line_format_md5 = md5_2[layer_idx][2*line_idx]
            page2_line_data_md5 = md5_2[layer_idx][2*line_idx + 1]

            # assume we don't have a match
            line_match = False

            # now loop through page 1 lines to check if a match exists
            for md5_idx in range(int(len(md5_1[layer_idx])/2)):
                page1_line_format_md5 = md5_1[layer_idx][2*md5_idx]
                page1_line_data_md5 = md5_1[layer_idx][2*md5_idx + 1]

                if page1_line_format_md5 == page2_line_format_md5 and page1_line_data_md5 == page2_line_data_md5:
                    # we have a match, no need to add
                    # print('Layer {} line {} ({}) match found ({})'.format(layer_idx, line_idx, page2_line_data_md5, md5_idx))
                    line_match = True
                    break

            # check if we have a match if not then add this line from page 2 to the merged page
            if not line_match:
                # add line to merged page
                # print('Adding line {} to merged page'.format(line_idx))
                merged_page.get_layers()[layer_idx].add_line(page_2.get_layers()[layer_idx].get_lines()[line_idx])

    return merged_page


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


    def write_metadata_json_file(self, metadata_json_file_path):
        metadata_dict = {'layers': []}
        for layer_idx, _ in enumerate(self._layers):
            metadata_dict['layers'].append({'name': 'Layer {}'.format(layer_idx + 1)})
        metadata_json = json.dumps(metadata_dict, indent=4)
        with open(metadata_json_file_path, 'w') as out_file:
            out_file.write(metadata_json)


class LineParser:
    def __init__(self, rm_file_path = None):
        self._rm_file_path = rm_file_path
        self._rm_file_binary_data = None
        self.layers_metadata = None


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

        # attempt to extract metadate file path
        metadata_file_path = self._rm_file_path[:-3] + '-metadata.json'

        if os.path.exists(metadata_file_path):
            with open(metadata_file_path, "r") as meta_file:
                self.layers_metadata = json.loads(meta_file.read())["layers"]
        else:
            self.layers_metadata = None


    # load in raw bytes/bytearray data and page metadata from zip file
    def read_rm_data_from_zip(self, id, zip_file, page_idx):
        with zip_file.open(name='{}/{}.rm'.format(id, page_idx), mode='r') as zip_data_file:
            zip_data = zip_data_file.read()

        if isinstance(zip_data, bytes) or isinstance(zip_data, bytearray):
            self._rm_file_binary_data = zip_data

        try:
            with zip_file.open(name='{}/{}-metadata.json'.format(id, page_idx), mode='r') as page_metadata:
                self.layers_metadata = json.loads(page_metadata.read())["layers"]
        except:
            self.layers_metadata = None


    def load_rm_data_binary(self, rm_data):
        if isinstance(rm_data, bytes) or isinstance(rm_data, bytearray):
            self._rm_file_binary_data = rm_data


    def load_layer_metadata(self, layer_metadata):
        if isinstance(layer_metadata, dict):
            self.layers_metadata = layer_metadata


    def parse_rm_data(self, calculate_MD5 = False):
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
        if self.layers_metadata is not None:
            for l in range(len(self.layers_metadata)):
                layer = self.layers_metadata[l]

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

        if calculate_MD5:
            # create a list to hold line MD5 checksums by layer
            MD5_list = []

        # parse each layer
        for layer in range(nlayers):
            this_layer = Layer()

            if calculate_MD5:
                # add an empty list to hold MD5 checksums for current layer
                MD5_list.append([])

            # read out number of strokes in current layer
            fmt = '<I'
            (num_lines,) = struct.unpack_from(fmt, self._rm_file_binary_data, offset)
            offset += struct.calcsize(fmt)

            # Iterate through the strokes in the layer (if there are any)
            for stroke in range(num_lines):
                if this_page._is_v3:
                    fmt = '<IIIfI'
                    fmt_len = 20
                    pen_nr, color, i_unk, width, segments_count = struct.unpack_from(fmt, self._rm_file_binary_data, offset)
                    offset += struct.calcsize(fmt)
                if this_page._is_v5:
                    fmt = '<IIIffI'
                    fmt_len = 24
                    pen_nr, color, i_unk, width, unknown, segments_count = struct.unpack_from(fmt, self._rm_file_binary_data, offset)
                    offset += struct.calcsize(fmt)

                # add layer header to byte array for md5 calculation
                if calculate_MD5:
                    # add the hash of the format string of the current line
                    MD5_list[-1].append(hashlib.md5(self._rm_file_binary_data[offset:offset + fmt_len]).hexdigest())

                    # create an empty byte array to hold the data for the present line
                    line_byte_array = bytearray()

                # last_width = 0

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

                    if calculate_MD5:
                        # add data for current point to our byte array representing the current line
                        line_byte_array.extend(self._rm_file_binary_data[offset:offset+24])

                    offset += struct.calcsize(fmt)

                    this_point = Point(x, y, speed, tilt, width, pressure)
                    this_line.add_point(this_point)

                # finished processing points, add this line to current layer
                this_layer.add_line(this_line)

                if calculate_MD5:
                    # append MD5 hash for current line
                    MD5_list[-1].append(hashlib.md5(line_byte_array).hexdigest())

            this_page.add_layer(this_layer)

        if calculate_MD5:
            return (this_page, MD5_list)
        else:
            return this_page

