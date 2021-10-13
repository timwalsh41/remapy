import tkinter
import tkinter.ttk as ttk
import tkinter.font as tkFont
from experimental import lines
from experimental import text_upload_sync
import model
import os
import glob

# Next steps
# - Write code to build zip file in text_upload_sync.py
#
# Note that you can access the x/y location of a placed label with lbl.place_info()

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

# vertical portion of canvas that will be displayed at any given time (the rest is scrollable)
CANVAS_SCROLL_Y_FRACTION = 0.6

TEXTBOX_FONT = 'calibri 18'

class TextEntry:
    def __init__(self, x, y, width, text):
        self.x = x
        self.y = y
        self.width = width
        self.text = text


class RemarkableEditor:
    def __init__(self, path=None, page=0):
        if not os.path.exists(path):
            raise Exception('Path {} not found'.format(path))

        self.path = path

        # get remarkable page files in path
        page_files = glob.glob(os.path.join(self.path, '*.rm'))
        self.num_pages = len(page_files)

        self.page_number = page

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

        # storage for added text - create an empty list for each page
        self.text_list = [[] for p in range(self.num_pages)]

        # storage for added label objects - create an empty list for each page
        self.labels = []

        # flag for existence of unsaved changes in the page
        self.unsaved_changes = False

        return


    def create_window(self):
        self.top = tkinter.Tk()
        self.top.title('remapy editor')
        self.frame = tkinter.Frame(self.top, width=lines.REMARKABLE_DISPLAY_MAX_X + 100,
                                   height=CANVAS_SCROLL_Y_FRACTION*lines.REMARKABLE_DISPLAY_MAX_Y)
        self.frame.pack(expand=True, fill=tkinter.BOTH)
        self.canvas = tkinter.Canvas(self.frame, bg="white", height=CANVAS_SCROLL_Y_FRACTION*lines.REMARKABLE_DISPLAY_MAX_Y,
                                width=lines.REMARKABLE_DISPLAY_MAX_X,
                                scrollregion=[0,0,lines.REMARKABLE_DISPLAY_MAX_X, lines.REMARKABLE_DISPLAY_MAX_Y])
        self.vbar = tkinter.Scrollbar(self.frame, orient=tkinter.VERTICAL)
        self.vbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
        self.vbar.config(command=self.canvas.yview)
        # self.canvas.config(yscrollcommand=self.vbar.set)
        self.canvas.config(yscrollcommand=self.on_scroll)

        # bind the single click, release, and drag events to manage text box creation and deletion
        self.canvas.bind('<Button-1>', self.left_click)
        self.canvas.bind('<ButtonRelease-1>', self.release_click)
        self.canvas.bind('<B1-Motion>', self.click_drag)
        # Windows & OSX
        # self.canvas.bind_all('<MouseWheel>', self.on_mousewheel)
        # X11
        self.canvas.bind_all('<Button-4>', self.on_mousewheel)  # scroll up
        self.canvas.bind_all('<Button-5>', self.on_mousewheel)  # scroll down

        self.last_button = ttk.Button(self.top, text='<<', command=self.last_page)
        self.next_button = ttk.Button(self.top, text='>>', command=self.next_page)
        self.page_label = ttk.Label(text='')
        self.debug_button = ttk.Button(self.top, text='Debug', command=self.debug)
        self.save_button = ttk.Button(self.top, text='Save', command=self.write_output)

        self.draw_remarkable_page()
        self.canvas.pack(side=tkinter.LEFT,expand=True,fill=tkinter.BOTH)
        self.last_button.pack(side=tkinter.LEFT)
        self.page_label.pack(side=tkinter.LEFT)
        self.next_button.pack(side=tkinter.LEFT)
        self.save_button.pack(side=tkinter.LEFT)
        self.debug_button.pack(side=tkinter.LEFT)

        self.update_page_label()

        self.textbox_font = tkFont.Font(family='Calibri', size=18)

        # self.debug_button.place(x=10,y=10)
        # self.save_button.place(x=100,y=10)


    def draw_remarkable_page(self):
        page_path = os.path.join(self.path, '{}.rm'.format(self.page_number))
        if not os.path.exists(page_path):
            raise Exception('Page path {} not found')

        self.rm_parser.set_file_path(page_path)
        self.rm_parser.read_rm_file()
        self.page = self.rm_parser.parse_rm_data()

        # draw page contents
        if self.canvas is not None:
            # draw remarkable line content
            for layer in self.page.get_layers():
                for line in layer.get_lines():
                    if line._pen_nr != lines.Pen.ERASER:
                        x, y = line.get_point_coordinates_as_list()
                        xy_list = [item for pair in zip(x, y) for item in pair]
                        self.canvas.create_line(*xy_list, width=line.get_points()[0].width*1.25)

            # add in any previously created text labels
            for txt in self.text_list[self.page_number]:
                # load in class variables used to create the label
                self.text_size[0] = txt.width
                self.start_coords[0] = txt.x
                self.start_coords[1] = txt.y

                # now draw the label and add it to self.labels
                self.create_label(txt.text)
        else:
            print('Unable to draw remarkable contents, call create_window() first')


    def clear_canvas(self):
        if self.canvas is not None:
            # delete all lines on canvas
            self.canvas.delete('all')

            # delete any labels that have been created
            # while len(self.labels) > 0:
            #    self.labels[0].destroy()
            #     self.labels.pop(0)


    def start_main_loop(self):
        if self.top is not None:
            self.top.mainloop()
        else:
            print('Unable to start main loop, call create_window() first')


    def draw_rectangle(self, end_coords):
        self.outline_box = self.canvas.create_rectangle(*self.start_coords, *end_coords)


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
                                      font=self.textbox_font, width=self.text_size[0]*TEXTBOX_WIDTH_DIVISOR)
        self.canvas.tag_bind(lbl, '<Button-3>', self.right_click)
        self.labels.append(lbl)


    def click_drag(self, event):
        # print('drag x = {}; y = {}'.format(event.x, event.y))

        # get the y-offset from the vertical scrollbar position
        vbar_offset = self.vbar.get()[0]

        if self.text_status == TEXT_START:
            # starting to drag
            self.text_status = TEXT_DRAGGING
            self.draw_rectangle((event.x, event.y + vbar_offset*lines.REMARKABLE_DISPLAY_MAX_Y))

            # print('{} ({},{})'.format(text_status, event.x, event.y))
        elif self.text_status == TEXT_DRAGGING:
            # continuing drag, update rectangle
            self.canvas.delete(self.outline_box)
            self.draw_rectangle((event.x, event.y + vbar_offset*lines.REMARKABLE_DISPLAY_MAX_Y))

            # print('{} ({},{})'.format(text_status, event.x, event.y))


    def release_click(self, event):
        # print('release x = {}; y = {}'.format(event.x, event.y))

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

                # print('({},{}); ({},{})'.format(*self.start_coords, *self.text_size))

                # create text box and grab focus
                self.text_box = tkinter.Text(self.top, height=self.text_size[1], width=self.text_size[0], font=TEXTBOX_FONT)
                self.text_box.place(x=self.start_coords[0], y=self.start_coords[1] - vbar_offset*lines.REMARKABLE_DISPLAY_MAX_Y)
                self.text_box.focus_set()
            else:
                # textbox too small
                self.text_status = TEXT_NONE

            # destroy rectangle
            self.canvas.delete(self.outline_box)
            # print('{} ({},{})'.format(text_status, event.x, event.y))


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


    def on_scroll(self, top, bottom):
        # top = position of top of scroll bar
        # bottom = position of bottom of scroll bar
        # range is 0-1
        self.vbar.set(top, bottom)


    def write_output(self):
        if self.unsaved_changes:
            for page in range(self.num_pages):
                if len(self.text_list[page]) > 0:
                    # get path to page file
                    page_path = os.path.join(self.path, '{}.rm'.format(self.page_number))
                    if not os.path.exists(page_path):
                        raise Exception('Page path {} not found')

                    # add our new text to the page file
                    text_upload_sync.add_strings_to_page(self.text_list[page], page_path)

            # re-draw current page so that text we added becomes remarkable objects rather than tkinter
            # labels
            self.clear_canvas()

            # clear local list of text labels
            self.text_list = [[] for p in range(self.num_pages)]

            # now redraw the page
            self.draw_remarkable_page()

            im = model.item_manager.ItemManager()

            # connect to RM server
            im.rm_client.sign_in()

            # increment version number
            text_upload_sync.increment_version_number(im, id)

            # we sync with local remarkable first as the remarkable now automatically updates a notebook version
            # number when a new version is posted to the cloud (even though it doesn't download the update)
            print('Sync to local')
            text_upload_sync.sync(im)

            # upload to server
            print('Upload to server')
            text_upload_sync.upload(im, id)



            self.unsaved_changes = False


    def debug(self):
        print('Entering debug mode')


    def next_page(self):
        if self.page_number < (self.num_pages - 1):
            self.clear_canvas()
            self.page_number += 1
            self.draw_remarkable_page()
            self.update_page_label()


    def last_page(self):
        if self.page_number > 0:
            self.clear_canvas()
            self.page_number -= 1
            self.draw_remarkable_page()
            self.update_page_label()


    def update_page_label(self):
        self.page_label.config(text='    Page {}/{}    '.format(self.page_number + 1, self.num_pages))


if __name__ == '__main__':
    # August '21 to-do
    # id = '4fea4460-0c02-466d-a31e-63f2eeb1a087'

    # Remarkable test
    id = '0e6ceff0-3137-4dcc-8672-ee63c32621e1'

    file_path = '/home/tim/.remapy/data/{}/{}/'.format(id, id)

    rema = RemarkableEditor(file_path, page=0)
    rema.create_window()
    rema.draw_remarkable_page()
    rema.start_main_loop()
