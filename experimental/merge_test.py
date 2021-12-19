from lines import LineParser
import lines
import copy

rm_file_path = r'/home/tim/.remapy/data/0e6ceff0-3137-4dcc-8672-ee63c32621e1/0e6ceff0-3137-4dcc-8672-ee63c32621e1/0.rm'
rm_file2_path = '/home/tim/Desktop/0.rm'

lp = LineParser(rm_file_path)
lp.read_rm_file()
(rm_page, md5) = lp.parse_rm_data(calculate_MD5=True)

print('Page 1 Layer 0 has {} objects in MD5'.format(len(md5[0])))

page_layer = rm_page.get_layers()[0]
print('Page 1 Layer 0 has {} lines'.format(len(page_layer.get_lines())))
print('Page 1 Layer 0 has {} 2xlines'.format(2*len(page_layer.get_lines())))

with open(rm_file_path, 'rb') as f:
    data = f.read()

# create a copy of the page
page_2 = copy.deepcopy(rm_page)

# add a line to this page
new_y = [200, 150, 250]
new_x = [700, 850, 1000]

# create the line as an array of Point objects
new_line = lines.Line(pen_nr=lines.Pen.BALLPOINT, color=0, i_unk=0, width=2.0)

for idx,x in enumerate(new_x):
    new_point = lines.Point(x, new_y[idx], speed=0.088, tilt=0.0009, width=2.96, pressure=0.9)
    new_line.add_point(new_point)

# add the line to the layer[0] array
page_2.get_layers()[0].add_line(new_line)

# write this page file out
page_2.write_output_file(rm_file2_path)

# now read back in with md5 array
lp.set_file_path(rm_file2_path)
lp.read_rm_file()
(page_2, md5_2) = lp.parse_rm_data(calculate_MD5=True)

print('Page 2 Layer 0 has {} objects in MD5'.format(len(md5_2[0])))

page_2_layer = page_2.get_layers()[0]
print('Page 2 Layer 0 has {} lines'.format(len(page_2_layer.get_lines())))
print('Page 2 Layer 0 has {} 2xlines'.format(2*len(page_2_layer.get_lines())))

merge_page = lines.merge_pages(rm_page, md5, page_2, md5_2)

# why are we getting last two lines copied in when we add one line
# - Maybe we are not segmenting the binary file data properly for md5 calculation?

pass