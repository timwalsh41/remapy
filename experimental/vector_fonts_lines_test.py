import fonts
import matplotlib.pyplot as plt

font = 'znikoslsvginot-font/Znikoslsvginot8-GOB3y.ttf'
# font = '/usr/share/fonts/truetype/freefont/FreeSans.ttf'

f = fonts.rm_font()
f.load_vector_alphabet(font)

#for i in range(33,127):
for i in range(101,102):
    new_lines = f.char_to_lines(chr(i))
    fig, ax = plt.subplots(figsize=(9,9))
    for line in new_lines:
        (x,y) = line.get_point_coordinates_as_list()
        ax.plot(x,y, lw=4)

    ax.axis('equal')
    plt.show()

