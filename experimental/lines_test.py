import lines
import matplotlib.pyplot as plt
import numpy as np
import fonts

file_path = '/home/tim/.remapy/data/0e6ceff0-3137-4dcc-8672-ee63c32621e1/0e6ceff0-3137-4dcc-8672-ee63c32621e1/'
rm_file = file_path + '0.rm'
output_file = file_path + '0.rm'

# source for the single line font file:
# https://www.fontspace.com/category/single-line
font_file = 'znikoslsvginot-font/Znikoslsvginot8-GOB3y.ttf'
# font_file = '/usr/share/fonts/truetype/freefont/FreeSans.ttf'

rm_parser = lines.LineParser(rm_file)
rm_parser.read_rm_file()
page = rm_parser.parse_rm_data()

f = fonts.rm_font()

# use this command to process in bitmap format
f.load_bitmap_alphabet(font_file)

# use this command to process in vector format
f.load_vector_alphabet(font_file)

fig,ax = plt.subplots()

# plot notebook page contents
for layer in page.get_layers():
    for line in layer.get_lines():
        if line._pen_nr != lines.Pen.ERASER:
            x,y = line.get_point_coordinates_as_list()
            x = np.array(x)
            y = np.array(y)
            ax.plot(x, -y, '-', color='blue', lw=4)

ax.axis('equal')

# now add a new line to the plot
# new_y = [-300, -250, -300]
# new_x = [700, 850, 1000]

# plt.plot(new_x, new_y, color='blue', lw=4)

# create the line as an array of Point objects
# new_line = lines.Line(pen_nr=lines.Pen.BALLPOINT, color=0, i_unk=0, width=2.0)

# for idx,x in enumerate(new_x):
#    new_point = lines.Point(x, new_y[idx], speed=0.088, tilt=0.0009, width=2.96, pressure=0.9)
#    new_line.add_point(new_point)

# add the line to the layer[0] array
# page.get_layers()[0].add_line(new_line)

# add a character to the page - bitmap format
# new_line = lines.matrix_to_line(f.alphabet['e'], offset_x = 625, offset_y = 350, x_scale=0.25, y_scale=-0.25)
# page.get_layers()[0].add_line(new_line)
# x,y = new_line.get_point_coordinates_as_list()
# plt.plot(x,y, '.', ms=4, color='blue')

# print('line count = {}'.format(page.get_layers()[0]._line_count))

# add a string to the page - vector format
spacing_dict = {}
#spacing_dict = {'a': 128, 'b': 160, 'c': 142, 'd': 192, 'e': 128, 'f': 92, 'g': 142, 'h': 192, 'i': 64,
#                'j': 64, 'k': 128, 'l': 64, 'm': 192, 'n': 168, 'o': 168, 'p': 168, 'q': 192, 'r': 128,
#                's': 128, 't': 128, 'u': 192, 'v': 128, 'w': 256, 'x': 128, 'y': 128, 'z': 128}
# new_string = 'abcdefghijklmnopqrstuvwxyz'
# new_string = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
# new_string = 'kjlakwmcijeijasgjeutrybalksrzbdjwbqlmvnbuqwilajd'
new_string = 'the quick brown fox jumps over the lazy dog'
# new_string = 'test'

offset_x = 200
offset_y = 200
scale = 0.008
for char in new_string:
    new_lines = f.char_to_lines(char, offset_x=offset_x, offset_y=offset_y, scale_x=scale, scale_y=-1*scale)
    for l in new_lines:
        x,y = l.get_point_coordinates_as_list()
        # plt.plot(x,y,color='blue', lw=4)
        page.get_layers()[0].add_line(l)
    if char in spacing_dict:
        offset_x += spacing_dict[char]*scale
    else:
        offset_x += f.face.glyph.advance.x*scale
    print('{}: {}'.format(char, f.face.glyph.advance.x))

# print('line count = {}'.format(page.get_layers()[0]._line_count))
plt.show()

# write the result out to the .rm file
# page.write_output_file(output_file)


