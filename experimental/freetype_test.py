from freetype import Face
from matplotlib import pyplot as plt
import numpy as np

# font = '/usr/share/fonts/truetype/freefont/FreeSans.ttf'
font = 'znikoslsvginot-font/Znikoslsvginot8-GOB3y.ttf'
char_to_plot = 'e'
bezier_approx = 100

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


face = Face(font)
face.set_char_size( 48*64 )
face.load_char(char_to_plot)

slot = face.glyph
outline = slot.outline

start, end = 0, 0

xy = pointsToList(outline.points, outline.tags)
#plt.plot(xy[0][0], xy[0][1], 'v')
#plt.plot(xy[1][0], xy[1][1], 'o')

for i in range(len(outline.contours)):
    end = outline.contours[i]

    if outline.tags[start] == 1:
        points = outline.points[start:end + 1]
        points.append(points[0])
        tags = outline.tags[start:end + 1]
        tags.append(tags[0])
    elif outline.tags[start] == 0:
        # first point is not on the curve
        if outline.tags[end] == 1:
            # last point of the contour is on the curve, use that as the start point
            points = outline.points[end]
            points.extend(outline.points[start:end + 1])
            tags = [1]
            tags.extend(outline.tags[start:end + 1])
        elif outline.tags[end] == 0:
            # last point of the contour is not on the curve, we will instead
            # interpolate between the first point and the last point and take
            # that as the start/end point on the curve
            C = ((outline.points[start][0] + outline.points[end][0])/2,
                 (outline.points[start][1] + outline.points[end][1])/2)
            points = [C]
            points.extend(outline.points[start:end + 1])
            points.append(C)
            tags = [1]
            tags.extend(outline.tags[start:end + 1])
            tags.append(1)

    segments = [[points[0], ], ]
    for j in range(1, len(points)):
        segments[-1].append(points[j])
        if tags[j] and j < (len(points) - 1):
            segments.append([points[j], ])

    # bezier curve independent variable
    t = np.linspace(0,1,bezier_approx)
    for segment in segments:
        if len(segment) == 2:
            # 2 points in segment - plot straight line
            plt.plot([segment[0][0], segment[1][0]], [segment[0][1], segment[1][1]])
        elif len(segment) == 3:
            # 3 points in segment - plot quadratic bezier
            (x,y) = quadraticBezier(t, *segment)
            plt.plot(x,y)
        else:
            # more than 3 points in segment - plot as a series of quadratic beziers,
            # where the end point of one intermediate curve and the start point of
            # the next is equal to the average of the two control points
            p_start = segment[0]
            for k in range(2, len(segment)-1):
                # calculate intermediate point
                p_intermediate = intermediatePoint(segment[k-1], segment[k])
                (x,y) = quadraticBezier(t, p_start, segment[k-1], p_intermediate)
                plt.plot(x,y)
                p_start = p_intermediate

            # now get the final point
            (x,y) = quadraticBezier(t, p_intermediate, segment[-2], segment[-1])
            plt.plot(x,y)

    start = end + 1

plt.axis('equal')
plt.show()
