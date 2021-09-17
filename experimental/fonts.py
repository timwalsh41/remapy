from PIL import Image, ImageFont
import freetype
import numpy as np
import os
from utils.helper import Singleton
from experimental.lines import Line, Point, Pen

# number of straight line segments to use in approximation of bezier curves
BEZIER_INDEX = 8

# font size for vector font
VECTOR_FONT_SIZE = 48*64

# settings to use for new Line creation
TILT = 0
SPEED = 1
PRESSURE = 1
WIDTH = 1.25

# quadratic bezier curve
# p0 = start point
# p1 = control point
# p2 = end point
# ref: https://stackoverflow.com/questions/5634460/quadratic-b%C3%A9zier-curve-calculate-points
def quadraticBezier(t, p0, p1, p2):
    x = (1 - t)**2*p0[0] + 2*(1-t)*t*p1[0] + t**2*p2[0]
    y = (1 - t)**2*p0[1] + 2*(1-t)*t*p1[1] + t**2*p2[1]

    return (x,y)


def intermediatePoint(p1, p2):
    return [(p1[0] + p2[0])/2,
            (p1[1] + p2[1])/2]


def pointsToList(points, tags):
    x1 = []
    y1 = []
    x0 = []
    y0 = []

    for idx, cur_point in enumerate(points):
        if tags[idx]:
            x1.append(cur_point[0])
            y1.append(cur_point[1])
        else:
            x0.append(cur_point[0])
            y0.append(cur_point[1])

    return [(x0,y0), (x1, y1)]


class rm_font(metaclass=Singleton):
    def __init__(self):
        # create our alphabet dictionary
        self.alphabet = {}
        self.face = None

    def load_bitmap_alphabet(self, font_path):
        if not os.path.exists(font_path):
            print('Error - invalid font file path: {}'.format(font_path))
            return

        point_size = 256
        font = ImageFont.truetype(font_path, point_size)

        self.alphabet = {}

        for char in range(32,127):
            im = Image.Image()._new(font.getmask(chr(char)))
            self.alphabet[chr(char)] = np.array(im.getdata()).reshape(im.size[1], im.size[0])


    def load_vector_alphabet(self, font_path):
        if not os.path.exists(font_path):
            print('Error - invalid font path: {}'.format(font_path))
            return

        self.face = freetype.Face(font_path)
        self.face.set_char_size(VECTOR_FONT_SIZE)


    # reference for extracting straight lines and bezier curves from freetype
    # glyph:
    # https://catherineh.github.io/programming/2018/02/01/text-to-svg-paths
    # https://stackoverflow.com/questions/3465809/how-to-interpret-a-freetype-glyph-outline-when-the-first-point-on-the-contour-is
    def char_to_lines(self, char, offset_x = 0, offset_y = 0, scale_x = 1, scale_y = 1):
        if self.face is None:
            print('Error - no vector font loaded')
            return

        try:
            self.face.load_char(char)
        except:
            print('Unable to load char {}'.format(char))

        outline = self.face.glyph.outline
        new_lines = []

        start, end = 0, 0

        # bezier curve independent variable
        t = np.linspace(0, 1, BEZIER_INDEX)

        for i in range(len(outline.contours)):
            # contours contains the indices of the end point of each contour
            end = outline.contours[i]

            # grab the points for each contour - how we process this depends if we start with a point
            # on the contour or a control point
            if outline.tags[start] == freetype.FT_CURVE_TAG_ON:
                # grab the contour points, appending the start point to the end so that
                # we draw a closed curve
                points = outline.points[start:end + 1]
                points.append(points[0])

                # do the same for the tags
                tags = outline.tags[start:end + 1]
                tags.append(tags[0])
            elif outline.tags[start] == freetype.FT_CURVE_TAG_CONIC:
                # first point is not on the curve
                if outline.tags[end] == freetype.FT_CURVE_TAG_ON:
                    # last point of the contour is on the curve, use that as the start point; no need
                    # to append the start point to the end as we are using the end point for the start
                    points = outline.points[end]
                    points.extend(outline.points[start:end + 1])

                    # do the same for the tag
                    tags = [freetype.FT_CURVE_TAG_ON]
                    tags.extend(outline.tags[start:end + 1])
                elif outline.tags[end] == freetype.FT_CURVE_TAG_CONIC:
                    # last point of the contour is not on the curve, we will instead
                    # interpolate between the first point and the last point and take
                    # that as the start/end point on the curve
                    C = ((outline.points[start][0] + outline.points[end][0]) / 2,
                         (outline.points[start][1] + outline.points[end][1]) / 2)
                    points = [C]
                    points.extend(outline.points[start:end + 1])
                    points.append(C)

                    # now do the same for the tags, assigning our interpolated start/end
                    # point as being on the curve
                    tags = [freetype.FT_CURVE_TAG_ON]
                    tags.extend(outline.tags[start:end + 1])
                    tags.append(freetype.FT_CURVE_TAG_ON)

            # segments will hold the individual straight line and bezier curve segments
            segments = [[points[0], ], ]
            for j in range(1, len(points)):
                segments[-1].append(points[j])
                if tags[j] == freetype.FT_CURVE_TAG_ON and j < (len(points) - 1):
                    segments.append([points[j], ])

            for segment in segments:
                rm_line = Line(pen_nr=Pen.BALLPOINT, color=0, i_unk=0, width=2.0)

                if len(segment) == 2:
                    # 2 points in segment - plot straight line
                    rm_line.add_point(Point(x=segment[0][0]*scale_x + offset_x, y=segment[0][1]*scale_y + offset_y,
                                            tilt=TILT, speed=SPEED, pressure=PRESSURE, width=WIDTH))
                    rm_line.add_point(Point(x=segment[1][0]*scale_x + offset_x, y=segment[1][1]*scale_y + offset_y,
                                            tilt=TILT, speed=SPEED, pressure=PRESSURE, width=WIDTH))
                    new_lines.append(rm_line)
                elif len(segment) == 3:
                    # 3 points in segment - plot quadratic bezier
                    (x, y) = quadraticBezier(t, *segment)

                    for k in range(len(x)):
                        rm_line.add_point(Point(x=x[k]*scale_x + offset_x, y=y[k]*scale_y + offset_y,
                                                tilt=TILT, speed=SPEED, pressure=PRESSURE, width=WIDTH))

                    new_lines.append(rm_line)
                else:
                    # more than 3 points in segment - plot as a series of quadratic beziers,
                    # where the end point of one intermediate curve and the start point of
                    # the next is equal to the average of the two control points
                    p_start = segment[0]
                    for k in range(2, len(segment) - 1):
                        # calculate intermediate point
                        p_intermediate = intermediatePoint(segment[k - 1], segment[k])
                        (x, y) = quadraticBezier(t, p_start, segment[k - 1], p_intermediate)

                        for m in range(len(x)):
                            rm_line.add_point(Point(x=x[m]*scale_x + offset_x, y=y[m]*scale_y + offset_y,
                                                    tilt=TILT, speed=SPEED, pressure=PRESSURE, width=WIDTH))
                        p_start = p_intermediate

                    # now get the final point
                    (x, y) = quadraticBezier(t, p_start, segment[-2], segment[-1])
                    for m in range(len(x)):
                        rm_line.add_point(Point(x=x[m]*scale_x + offset_x, y=y[m]*scale_y + offset_y,
                                                tilt=TILT, speed=SPEED, pressure=PRESSURE, width=WIDTH))
                    new_lines.append(rm_line)

            start = end + 1

        return new_lines


