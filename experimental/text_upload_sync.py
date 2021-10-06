from experimental import lines
import matplotlib.pyplot as plt
import numpy as np
from experimental import fonts
import model.item_manager
from experimental import synchronizer
import os
from zipfile import ZipFile
import zipfile
from io import BytesIO
import json

# Script configuration options

# remapy ID of the document we'll modify
test_id = '0e6ceff0-3137-4dcc-8672-ee63c32621e1'

# path to local version of file for modification
local_remapy_item_path = '/home/tim/.remapy/data/' + test_id + '/' + test_id + '/'
rm_file = '0.rm'

# true-type font file to use for characters
# font_file = 'AovelSansRounded-rdDL.ttf'
font_file = '/usr/share/fonts/truetype/freefont/FreeSans.ttf'
vector_font_file = 'znikoslsvginot-font/Znikoslsvginot8-GOB3y.ttf'

# temporary value to advance in y-direction on new line
# TODO: update this with a proper value based on font size
Y_ADVANCE = 24

# empirically determined constants to convert size in pixels to
# size in characters for creating text box
# TODO: Update this with a proper constant based on font size
TEXTBOX_WIDTH_DIVISOR = 15
TEXTBOX_HEIGHT_DIVISOR = 29

# scale factor for font character to remarkable line object
SCALE = 0.008

# x-y coordinates to add a line to the page, just make these empty lists to skip
line_y = [300, 250, 300]
line_x = [700, 850, 1000]

# details for adding character
character = 'A'
character_x = 625
character_y = 450


# Support functions
def add_string(page, font, str, x, y, width):
    if len(str) == 0:
        return

    width *= TEXTBOX_WIDTH_DIVISOR

    offset_x = x
    offset_y = y

    max_x = min(x + width, lines.REMARKABLE_DISPLAY_MAX_X)

    words = str.split(' ')
    for word in words:
        # check width of the current word
        word_width = 0
        break_word = False

        for char in word:
            font.face.load_char(char)
            word_width += font.face.glyph.advance.x * SCALE

        if word_width > width:
            # word does not fit on a full line, so we'll need to break it up across
            # lines
            break_word = True
        elif word_width + offset_x > max_x:
            # word fits on a single line, but does not fit in the room remaining on this line
            # add a line feed and carriage return by resetting the x offset and advancing the y offset
            offset_x = x
            # TODO: Figure out y-advance from glyph/face
            # offset_y += font.face.glyph.advance.y * scale
            offset_y += Y_ADVANCE

        # now add each character individually
        for char in word:
            if char == '\n':
                # line feed and carriage return
                offset_x = x
                # TODO: update y-advance code
                # offset_y += font.face.glyph.advance.y * scale
                offset_y += Y_ADVANCE
            else:
                # print('{}: {}'.format(offset_x, char))
                font.face.load_char(char)
                if break_word and (offset_x + font.face.glyph.advance.x * SCALE) > max_x:
                    # line feed and carriage return
                    offset_x = x
                    # TODO: update y-advance code
                    # offset_y += font.face.glyph.advance.y * scale
                    offset_y += Y_ADVANCE
                add_character(page, font, char, offset_x, offset_y, SCALE, -1 * SCALE)

                # advance the cursor (note that the font object holds the previous loaded character in memory,
                # so we're advancing the appropriate amount
                offset_x += font.face.glyph.advance.x * SCALE

        # add a space at the end of the word
        font.face.load_char(' ')
        if (offset_x + font.face.glyph.advance.x * SCALE) > max_x:
            # line feed and carriage return
            offset_x = x
            offset_y += font.face.glyph.advance.y * SCALE
        else:
            # advance the width of a space
            offset_x += font.face.glyph.advance.x * SCALE


def add_strings_to_page(text_list, page_path):
    # load remarkable page data
    rm_parser = lines.LineParser(page_path)
    rm_parser.read_rm_file()
    page = rm_parser.parse_rm_data()

    # open up our font
    f = fonts.rm_font()
    f.load_vector_alphabet(vector_font_file)

    # now add strings one by one to the page
    for txt in text_list:
        add_string(page, f, txt.text, txt.x, txt.y, txt.width)

    # now write the output back out
    page.write_output_file(page_path)


def add_character(page, font, char, x, y, xscale, yscale):
    new_lines = font.char_to_lines(char, offset_x=x, offset_y=y, scale_x=xscale, scale_y=yscale)
    for l in new_lines:
        page.get_layers()[0].add_line(l)


def add_lines_and_characters():
    # open a LineParser for the target rm file
    full_rm_path = local_remapy_item_path + rm_file
    rm_parser = lines.LineParser(full_rm_path)
    rm_parser.read_rm_file()
    page = rm_parser.parse_rm_data()

    # open up our font
    f = fonts.rm_font()
    f.load_bitmap_alphabet(font_file)

    # plot notebook page contents
    fig,ax = plt.subplots()
    for layer in page.get_layers():
        for line in layer.get_lines():
            if line._color != 2:
                x,y = line.get_point_coordinates_as_list()
                x = np.array(x)
                y = np.array(y)
                ax.plot(x, -y, '.', color='blue', ms=4)
    ax.axis('equal')

    # add to our plot
    y = np.array(line_y)*-1
    ax.plot(line_x, y, color='blue', lw=4)

    # create the line as an array of Point objects
    new_line = lines.Line(pen_nr=lines.Pen.BALLPOINT, color=0, i_unk=0, width=2.0)

    for idx,x in enumerate(line_x):
        new_point = lines.Point(x, line_y[idx], speed=0.088, tilt=0.0009, width=2.96, pressure=0.9)
        new_line.add_point(new_point)

    # add the line to the layer[0] array
    page.get_layers()[0].add_line(new_line)

    # now add a character to the page
    new_line = lines.matrix_to_line(f.alphabet[character], offset_x=offset_x, offset_y=offset_y, x_scale=0.25,
                                    y_scale=-0.25)
    page.get_layers()[0].add_line(new_line)

    x,y = new_line.get_point_coordinates_as_list()
    y = np.array(y)*-1
    plt.plot(x,y, '.', ms=4, color='blue')

    plt.show()

    # now write the output back out
    page.write_output_file(full_rm_path)


def read_zip_file(id, root_folder):
    zip_file_path = root_folder + '/' + id + '.zip'
    # with open("test.zip", "wb") as f:
    #     f.write(mf.getvalue())
    print(zip_file_path)

    try:
        with open(zip_file_path, 'rb') as f:
            data = f.read()
    except:
        print('Error reading zip file')
        data = None
    return data


def build_zip_file(id, root_folder):
    mf = BytesIO()
    mf.seek(0)

    # open up the content file
    with open(os.path.join(root_folder, id + '.content')) as content_file:
        content_data = json.load(content_file)

    # extract the page ids
    # page_list = content_data['pages']

    with ZipFile(mf, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for root, directories, files in os.walk(root_folder):
            if id + '/.remapy' in root:
                continue
            for filename in files:
                # join the two strings in order to form the full filepath.
                filepath = os.path.join(root, filename)

                if '-metadata.json' in filepath:
                    # extract the page numer/index from the page filename
                    page_index = int(filename.split('.')[0].split('-')[0])

                    # for .rm page files and page metadata files, copy the file
                    # into a temporary object so that we can create a custom name
                    # that matches the ReMarkable format
                    with open(filepath, 'r') as file_obj:
                        # zf.writestr('{}/{}-metadata.json'.format(id, page_list[page_index]), file_obj.read())
                        zf.writestr('{}/{}-metadata.json'.format(id, page_index), file_obj.read())
                elif '.rm' in filepath:
                    # extract the page number/index from the page filename
                    page_index = int(filename.split('.')[0])

                    # for .rm page files and page metadata files, copy the file
                    # into a temporary object so that we can create a custom name
                    # that matches the ReMarkable format
                    with open(filepath, 'rb') as file_obj:
                        # zf.writestr('{}/{}.rm'.format(id, page_list[page_index]), file_obj.read())
                        zf.writestr('{}/{}.rm'.format(id, page_index), file_obj.read())
                else:
                    # standard file - just add directly to the zip
                    with open(filepath, 'r') as file_obj:
                        zf.writestr(filename, file_obj.read())

    mf.seek(0)
    return mf


def upload_request(im, id, metadata):
    response = im.rm_client._request("PUT", "/document-storage/json/2/upload/request",
                             body=[{
                                 "ID": id,
                                 "Type": "DocumentType",
                                 "Version": metadata["Version"]
                             }])

    return response


def upload(im, id):
    item = im.get_item(id=id)

    # update document version in metadata
    item.metadata["Version"] += 1
    print('New item version is {}'.format(item.metadata["Version"]))

    # write out the metadata with updated version to our local file
    item._write_metadata()

    # build zip file
    mf = build_zip_file(id, item.path)

    if mf is not None:
        response = upload_request(im, id, item.metadata)

        if response.ok:
            BlobURL = response.json()[0].get('BlobURLPut')

            response = im.rm_client._request('PUT', BlobURL, data=mf)
            retval = im.rm_client.update_metadata(item.metadata)
            print(retval)
            print(response.ok)


def sync(im):
    syncro = synchronizer.Synchronizer(ip=synchronizer.REMARKABLE_IP, password=synchronizer.REMARKABLE_PASSWORD)
    syncro.connect_ssh()

    if syncro.is_connected():
        im.traverse_tree(fun=syncro.local_sync, document=True, collection=False)

    syncro.disconnect()


# Main execution
if __name__ == '__main__':
    im = model.item_manager.ItemManager()

    # connect to RM server
    im.rm_client.sign_in()
    # root = im.get_root()

    # modify our page
    add_lines_and_characters()

    # upload to server
    upload(im)

    # sync with local remarkable
    sync(im)