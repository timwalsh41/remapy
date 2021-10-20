import tkinter
import tkinter.ttk as ttk
import tkinter.font as tkFont
from experimental import lines
import zipfile
from io import BytesIO
from experimental import fonts
import os
import glob

# state tracker for temporary text box for text entry
TEXT_NONE = 0
TEXT_START = 1
TEXT_DRAGGING = 2
TEXT_ACTIVE = 3

# minimum textbox size, in pixels
MIN_TEXTBOX_X = 50
MIN_TEXTBOX_Y = 10

# empirically determined constants to convert size in pixels to
# size in characters for creating text box
TEXTBOX_WIDTH_DIVISOR = 15
TEXTBOX_HEIGHT_DIVISOR = 29

# temporary value to advance in y-direction on new line
# TODO: update this with a proper value based on font size
Y_ADVANCE = 24

# scale factor for font character to remarkable line object
SCALE = 0.008

# font file to use for writing characters to remarkable pages
VECTOR_FONT_FILE = 'znikoslsvginot-font/Znikoslsvginot8-GOB3y.ttf'

# vertical portion of canvas that will be displayed at any given time (the rest is scrollable)
CANVAS_SCROLL_Y_FRACTION = 0.6

TEXTBOX_FONT = 'calibri 18'

# TextEntry class stores details of the text added by the user (x/y location, width of text, and text itself)
class TextEntry:
    def __init__(self, x, y, width, text):
        self.x = x
        self.y = y
        self.width = width
        self.text = text


# RemarkabelEditor class implements a standalone Tkinter window that renders a Remarkable notebook and allows
# the user to edit it by adding new text
class RemarkableEditor:
    def __init__(self, id=None, path=None, page=0, sync_fun=None, im=None):
        if not os.path.exists(path):
            raise Exception('Path {} not found'.format(path))

        # caller will provide the remapy ID of the notebook to be edited, the path to the notebook, a
        # function to call to sync the notebook to a locally connected Remarkable tablet, and the main
        # item manager
        self.id = id
        self.path = path
        self.sync_fun = sync_fun
        self.im = im

        # get remarkable page files in path
        page_files = glob.glob(os.path.join(self.path, '*.rm'))
        self.num_pages = len(page_files)

        # we will start by opening the page provided by the caller
        self.page_number = page

        # set up a LinesParser object to manage parsing and rendering the contents of
        # each Remarkable page file
        self.rm_parser = lines.LineParser()

        # state for text editing state machine
        self.text_status = TEXT_NONE

        # tkinter canvas object
        self.canvas = None

        # temporary outline box that is drawn while mouse is dragged to
        # create text edit area
        self.outline_box = None

        # editable text box object handle
        self.text_box = None

        # coordinates of the starting point for dragging to define the
        # editable text box
        self.start_coords = [0,0]

        # textbox dimensions
        self.text_size = [0,0]

        # create empty list for user text entries - create an empty list for each page
        self.text_list = [[] for p in range(self.num_pages)]

        # storage for added label objects that display the user added text until it is written into the
        # Remarkable page files
        self.labels = []

        # flag for existence of unsaved changes in the page
        self.unsaved_changes = False

        return


    # create_window creates the Tkinter window and controls for the editor
    def create_window(self):
        self.top = tkinter.Tk()
        self.top.title('RemaPy Editor')

        self.textbox_font = tkFont.Font(family='Calibri', size=18)

        self.frame = tkinter.Frame(self.top, width=lines.REMARKABLE_DISPLAY_MAX_X + 100,
                                   height=CANVAS_SCROLL_Y_FRACTION*lines.REMARKABLE_DISPLAY_MAX_Y)

        self.canvas = tkinter.Canvas(self.frame, bg="white", height=CANVAS_SCROLL_Y_FRACTION*lines.REMARKABLE_DISPLAY_MAX_Y,
                                width=lines.REMARKABLE_DISPLAY_MAX_X,
                                scrollregion=[0,0,lines.REMARKABLE_DISPLAY_MAX_X, lines.REMARKABLE_DISPLAY_MAX_Y])
        self.vbar = tkinter.Scrollbar(self.frame, orient=tkinter.VERTICAL)
        self.vbar.config(command=self.canvas.yview)
        # self.canvas.config(yscrollcommand=self.vbar.set)
        self.canvas.config(yscrollcommand=self.on_scroll)

        # bind the single click, release, and drag events to manage text box creation and deletion
        self.canvas.bind('<Button-1>', self.left_click)
        self.canvas.bind('<ButtonRelease-1>', self.release_click)
        self.canvas.bind('<B1-Motion>', self.click_drag)
        # TODO: Windows & OSX mousewheel binding
        # self.canvas.bind_all('<MouseWheel>', self.on_mousewheel)
        # X11 mousewheel:
        self.canvas.bind_all('<Button-4>', self.on_mousewheel)  # scroll up
        self.canvas.bind_all('<Button-5>', self.on_mousewheel)  # scroll down

        button_frame = tkinter.Frame(self.top)
        self.last_button = ttk.Button(button_frame, text='<<', command=self.last_page)
        self.next_button = ttk.Button(button_frame, text='>>', command=self.next_page)
        self.page_label = ttk.Label(button_frame, text='    Page {}/{}    '.format(self.page_number, self.num_pages))
        self.debug_button = ttk.Button(button_frame, text='Debug', command=self.debug)
        self.save_button = ttk.Button(button_frame, text='Save', command=self.write_output)
        self.exit_button = ttk.Button(button_frame, text='Close', command=self.exit)

        # draw the remarkable page contents for the current page
        self.draw_remarkable_page()

        button_frame.pack(side=tkinter.TOP, fill=tkinter.X)
        self.last_button.pack(side=tkinter.LEFT)
        self.page_label.pack(side=tkinter.LEFT)
        self.next_button.pack(side=tkinter.LEFT)
        self.save_button.pack(side=tkinter.LEFT)
        self.exit_button.pack(side=tkinter.LEFT)
        self.debug_button.pack(side=tkinter.LEFT)
        self.frame.pack(side=tkinter.BOTTOM, expand=True, fill=tkinter.BOTH)
        self.vbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
        self.canvas.pack(side=tkinter.BOTTOM, expand=True, fill=tkinter.BOTH)

        self.update_page_label()


    # draw_remarkable_page uses the LineParser object to add the Remarkable page contents to the canvas
    def draw_remarkable_page(self):
        page_path = os.path.join(self.path, '{}.rm'.format(self.page_number))
        if not os.path.exists(page_path):
            raise Exception('Page path {} not found')

        self.rm_parser.set_file_path(page_path)
        self.rm_parser.read_rm_file()
        self.page = self.rm_parser.parse_rm_data()

        # draw page contents
        if self.canvas is not None:
            # draw remarkable line content for each layer in the page
            for layer in self.page.get_layers():
                for line in layer.get_lines():
                    if line._pen_nr != lines.Pen.ERASER:
                        x, y = line.get_point_coordinates_as_list()
                        xy_list = [item for pair in zip(x, y) for item in pair]
                        self.canvas.create_line(*xy_list, width=line.get_points()[0].width*1.25)

            # add in any previously created text labels (e.g. for when we are switching amongst pages with
            # text additions)
            for txt in self.text_list[self.page_number]:
                # load in class variables used to create the label
                self.text_size[0] = txt.width
                self.start_coords[0] = txt.x
                self.start_coords[1] = txt.y

                # now draw the label and add it to self.labels
                self.create_label(txt.text)
        else:
            print('Unable to draw remarkable contents, call create_window() first')


    # clear_canvas deletes all Remarkable page content from the canvas
    def clear_canvas(self):
        if self.canvas is not None:
            # delete all lines on canvas
            self.canvas.delete('all')


    # start_main_loop starts the Tkinter main loop for the editor
    def start_main_loop(self):
        if self.top is not None:
            self.top.mainloop()
        else:
            print('Unable to start main loop, call create_window() first')


    # draw_rectangle creates the rectangle that represents the user editable text area as it is
    # being drawn by left clicking and dragging
    def draw_rectangle(self, end_coords):
        self.outline_box = self.canvas.create_rectangle(*self.start_coords, *end_coords)


    # left_click is called for a left mouseclick on the canvas, this function manages the start of the act of
    # drawing a text box, as well as clicking outside the text box once editing is complete
    def left_click(self, event):
        # print('click x = {}; y = {}'.format(event.x, event.y))

        if self.text_status == TEXT_NONE:
            # click event may be the start of a drag event to create a textbox
            self.text_status = TEXT_START

            # get the y-offset from the vertical scrollbar position
            vbar_offset = self.vbar.get()[0]

            # record the start position
            self.start_coords = [event.x, event.y + vbar_offset*lines.REMARKABLE_DISPLAY_MAX_Y]

            # print('{} ({},{})'.format(text_status, event.x, event.y))
        elif self.text_status == TEXT_ACTIVE:
            # click event outside of text box, reset state
            self.text_status = TEXT_NONE
            self.save_text()


    # save_text will save the contents of a newly finished text entry by the user into the Remarkable editor
    # TextEntry list, and then destroy the text box from the canvas
    def save_text(self):
        new_string = (self.text_box.get('1.0', 'end'))

        if len(new_string.strip()) > 0:
            # create a new label with the text
            self.create_label(new_string)

            # store the text for later addition to rm notebook
            self.text_list[self.page_number].append(TextEntry(x=self.start_coords[0], y=self.start_coords[1],
                                            width=self.text_size[0], text=new_string))

            self.unsaved_changes = True

        # destroy text box
        self.text_box.destroy()
        self.text_box = None


    # create_label draws a user text entry as a non-editable text label after the user has finished entry
    def create_label(self, new_string):
        # get the y-offset from the vertical scrollbar position
        vbar_offset = self.vbar.get()[0]

        # compute adjusted y position to display correctly on scrolled canvas
        # y_adjusted = self.start_coords[1] - vbar_offset*lines.REMARKABLE_DISPLAY_MAX_Y

        # lbl = ttk.Label(self.top, text=new_string, width=self.text_size[0], font=TEXTBOX_FONT,
        #                wraplength=self.text_size[0] * TEXTBOX_WIDTH_DIVISOR, background="white")
        # lbl.bind('<Button-3>', self.right_click)
        # lbl.place(x=self.start_coords[0], y=y_adjusted)

        lbl = self.canvas.create_text(self.start_coords[0], self.start_coords[1], text=new_string, anchor=tkinter.NW,
                                      font=TEXTBOX_FONT, width=self.text_size[0]*TEXTBOX_WIDTH_DIVISOR)
        # TODO: why isn't TkFont/self.textbox_font working here; it only works when running editor.py
        # as __main__
        # self.canvas.itemconfigure(lbl, font=self.textbox_font)
        self.canvas.tag_bind(lbl, '<Button-3>', self.right_click)
        self.labels.append(lbl)


    # click_drag draws the rectangle representing the text editing area as the user drags the mouse to
    # define the text box
    def click_drag(self, event):
        # print('drag x = {}; y = {}'.format(event.x, event.y))

        # get the y-offset from the vertical scrollbar position
        vbar_offset = self.vbar.get()[0]

        if self.text_status == TEXT_START:
            # starting to drag
            self.text_status = TEXT_DRAGGING
            self.draw_rectangle((event.x, event.y + vbar_offset*lines.REMARKABLE_DISPLAY_MAX_Y))
        elif self.text_status == TEXT_DRAGGING:
            # continuing drag, update rectangle
            self.canvas.delete(self.outline_box)
            self.draw_rectangle((event.x, event.y + vbar_offset*lines.REMARKABLE_DISPLAY_MAX_Y))


    # release_click creates a text box when the user is finished dragging the mouse to define the
    # editing area
    def release_click(self, event):
        if self.text_status == TEXT_START:
            # no drag = no text box, just reset state
            self.text_status = TEXT_NONE

            # print('{} ({},{})'.format(text_status, event.x, event.y))
        elif self.text_status == TEXT_DRAGGING:
            # finished dragging - check if we have a valid box
            if abs(self.start_coords[0] - event.x) >= MIN_TEXTBOX_X and \
                    abs(self.start_coords[1] - event.y) >= MIN_TEXTBOX_Y:
                # valid textbox size - create textbox
                self.text_status = TEXT_ACTIVE

                # get the y-offset from the vertical scrollbar position
                vbar_offset = self.vbar.get()[0]

                event_y_adjusted = event.y + vbar_offset*lines.REMARKABLE_DISPLAY_MAX_Y

                self.text_size[0] = int(abs(self.start_coords[0] - event.x) / TEXTBOX_WIDTH_DIVISOR)
                self.text_size[1] = int(abs(self.start_coords[1] - event_y_adjusted) / TEXTBOX_HEIGHT_DIVISOR)

                self.start_coords[0] = min(self.start_coords[0], event.x)
                self.start_coords[1] = min(self.start_coords[1], event_y_adjusted)

                # create text box and grab focus
                self.text_box = tkinter.Text(self.top, height=self.text_size[1], width=self.text_size[0], font=TEXTBOX_FONT)
                self.text_box.place(x=self.start_coords[0], y=self.start_coords[1] - vbar_offset*lines.REMARKABLE_DISPLAY_MAX_Y)
                self.text_box.focus_set()
            else:
                # textbox too small
                self.text_status = TEXT_NONE

            # destroy rectangle
            self.canvas.delete(self.outline_box)


    # right_click handles deleting text labels (and the corresponding TextEntry) when the user right
    # clicks on the label
    def right_click(self, event):
        # get the closest object on the canvas to the right click
        closest_object = event.widget.find_closest(event.x, event.y)[0]
        if closest_object in self.labels:
            # get index of label
            idx = [i for i in range(len(self.labels))
                   if self.labels[i] == closest_object][0]

            # delete text entry from list
            self.text_list[self.page_number].pop(idx)
            self.labels.remove(closest_object)

            # remove label from canvas
            self.canvas.delete(closest_object)


    # on_mousewheel handles scrolling the canvas when the user actuates the mousewheel
    def on_mousewheel(self, event):
        # mousewheel event - windows & OSX (for OSX, remove the 120 scale factor)
        # self.canvas.yview_scroll(-1 * int(event.delta / 120), "units")

        # X11 - we have mouse button 4 and 5
        if event.num == 4:
            # scroll up
            direction = -1
        elif event.num == 5:
            # scroll down
            direction = 1

        self.canvas.yview_scroll(direction, 'units')


    # on_scroll updates the vertical scrollbar position when the canvas is scrolled
    def on_scroll(self, top, bottom):
        # top = position of top of scroll bar
        # bottom = position of bottom of scroll bar
        # range is 0-1
        self.vbar.set(top, bottom)


    # add_character converts a character from a truetype font to remarkable lines format and
    # writes it to a remarkable page
    def add_character(self, page, font, char, x, y, xscale, yscale):
        new_lines = font.char_to_lines(char, offset_x=x, offset_y=y, scale_x=xscale, scale_y=yscale)
        for l in new_lines:
            page.get_layers()[0].add_line(l)


    # add_string writes a text string to a remarkable page file
    def add_string(self, page, font, str, x, y, width):
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
                    self.add_character(page, font, char, offset_x, offset_y, SCALE, -1 * SCALE)

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


    def add_strings_to_page(self, page_number, page_path):
        # load remarkable page data
        rm_parser = lines.LineParser(page_path)
        rm_parser.read_rm_file()
        page = rm_parser.parse_rm_data()

        # open up our font
        this_folder = os.path.dirname(os.path.abspath(__file__))
        absolute_font_path = os.path.join(this_folder, VECTOR_FONT_FILE)
        f = fonts.rm_font()
        f.load_vector_alphabet(absolute_font_path)

        # now add strings one by one to the page
        for txt in self.text_list[page_number]:
            self.add_string(page, f, txt.text, txt.x, txt.y, txt.width)

        # now write the output back out
        page.write_output_file(page_path)


    # write_output is called when the user clicks the save button; assuming there is new text to save, this
    # function adds that text to the Remarkable page files, redraws the canvas, and then uploads the new
    # page data to the Remarkable cloud and triggers a local sync in the file manager
    def write_output(self):
        if self.unsaved_changes:
            for page_number in range(self.num_pages):
                if len(self.text_list[page_number]) > 0:
                    # get path to page file
                    page_path = os.path.join(self.path, '{}.rm'.format(page_number))
                    if not os.path.exists(page_path):
                        raise Exception('Page path {} not found')

                    # add our new text to the page file
                    self.add_strings_to_page(page_number, page_path)

            # re-draw current page so that text we added becomes remarkable objects rather than tkinter
            # labels
            self.clear_canvas()

            # clear local list of text labels
            self.text_list = [[] for p in range(self.num_pages)]

            # now redraw the page
            self.draw_remarkable_page()

            # increment version number
            self.im.get_item(self.id).increment_version_number()

            # upload to server
            print('Upload to server')
            self.upload()

            # trigger a local sync of the edited file in the file explorer
            self.sync_fun()

            self.unsaved_changes = False


    # build_zip_file will create a zip archive of the Remarkable notebook as a BytesIO object
    # suitable for uploading to the Remarkable cloud
    def build_zip_file(self, root_folder):
        mf = BytesIO()
        mf.seek(0)

        # open up the content file
        # with open(os.path.join(root_folder, self.id + '.content')) as content_file:
        #     content_data = json.load(content_file)

        # extract the page ids
        # page_list = content_data['pages']

        with zipfile.ZipFile(mf, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
            for root, directories, files in os.walk(root_folder):
                if self.id + '/.remapy' in root:
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
                            # zf.writestr('{}/{}-metadata.json'.format(self.id, page_list[page_index]), file_obj.read())
                            zf.writestr('{}/{}-metadata.json'.format(self.id, page_index), file_obj.read())
                    elif '.rm' in filepath:
                        # extract the page number/index from the page filename
                        page_index = int(filename.split('.')[0])

                        # for .rm page files and page metadata files, copy the file
                        # into a temporary object so that we can create a custom name
                        # that matches the ReMarkable format
                        with open(filepath, 'rb') as file_obj:
                            # zf.writestr('{}/{}.rm'.format(self.id, page_list[page_index]), file_obj.read())
                            zf.writestr('{}/{}.rm'.format(self.id, page_index), file_obj.read())
                    else:
                        # standard file - just add directly to the zip
                        with open(filepath, 'r') as file_obj:
                            zf.writestr(filename, file_obj.read())

        mf.seek(0)
        return mf


    # upload_request sends the initial request to the Remarkable server to upload the notebook
    def upload_request(self, metadata):
        response = self.im.rm_client._request("PUT", "/document-storage/json/2/upload/request",
                                         body=[{
                                             "ID": self.id,
                                             "Type": "DocumentType",
                                             "Version": metadata["Version"]
                                         }])

        return response


    # upload will build a zip file of the Remarkable notebook document and upload it to
    # the Remarkable cloud
    def upload(self):
        item = self.im.get_item(id=self.id)

        # build zip file
        mf = self.build_zip_file(item.path)

        if mf is not None:
            response = self.upload_request(item.metadata)

            if response.ok:
                BlobURL = response.json()[0].get('BlobURLPut')

                response = self.im.rm_client._request('PUT', BlobURL, data=mf)
                retval = self.im.rm_client.update_metadata(item.metadata)
                print(retval)
                print(response.ok)


    # exit will close the main editor window to end the session
    def exit(self):
        self.top.destroy()


    # debug is a test function to enter a debug prompt
    def debug(self):
        print('Entering debug mode')


    # next_page moves to the next page in the notebook, clearing the canvas and then drawing
    # the contents of the new page
    def next_page(self):
        if self.page_number < (self.num_pages - 1):
            self.clear_canvas()
            self.page_number += 1
            self.draw_remarkable_page()
            self.update_page_label()


    # last_page moves to the previous page in the notebook, clearing the canvas and then drawing
    # the contents of the new page
    def last_page(self):
        if self.page_number > 0:
            self.clear_canvas()
            self.page_number -= 1
            self.draw_remarkable_page()
            self.update_page_label()


    # update_page_label updates the page number label when the page is switched
    def update_page_label(self):
        self.page_label.config(text='    Page {}/{}    '.format(self.page_number + 1, self.num_pages))


if __name__ == '__main__':
    # August '21 to-do
    # id = '4fea4460-0c02-466d-a31e-63f2eeb1a087'

    # Remarkable test
    id = '0e6ceff0-3137-4dcc-8672-ee63c32621e1'

    file_path = '/home/tim/.remapy/data/{}/{}/'.format(id, id)

    rema = RemarkableEditor(id, file_path, page=0)
    rema.create_window()
    rema.start_main_loop()
