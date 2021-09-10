from PIL import Image, ImageFont
import numpy as np
import matplotlib.pyplot as plt

font_file = 'AovelSansRounded-rdDL.ttf'

point_size = 96
font = ImageFont.truetype(font_file, point_size)

im = Image.Image()._new(font.getmask('abcdefghijklmnopqrstuvwxyz'))
# im.show()

d = np.array(im.getdata()).reshape(im.size[1], im.size[0])
plt.imshow(d)
plt.show()