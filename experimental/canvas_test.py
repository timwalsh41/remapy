import tkinter
import tkinter.ttk as ttk
import lines
import text_upload_sync
import model

# Next steps
# - Write code to build zip file in text_upload_sync.py
#
# Note that you can access the x/y location of a placed label with lbl.place_info()

file_path = '/home/tim/.remapy/data/0e6ceff0-3137-4dcc-8672-ee63c32621e1/0e6ceff0-3137-4dcc-8672-ee63c32621e1/'
rm_file = file_path + '0.rm'

rm_parser = lines.LineParser(rm_file)
rm_parser.read_rm_file()
page = rm_parser.parse_rm_data()

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

TEXTBOX_FONT = 'calibri 18'

class TextEntry:
    def __init__(self, x, y, width, text):
        self.x = x
        self.y = y
        self.width = width
        self.text = text


class RemarkableEditor:

    def __init__(self):
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

        # storage for added labels
        self.text_list = []

        return


    def create_window(self):
        self.top = tkinter.Tk()
        self.top.title('remapy')
        self.canvas = tkinter.Canvas(self.top, bg="white", height=lines.REMARKABLE_DISPLAY_MAX_Y,
                                width=lines.REMARKABLE_DISPLAY_MAX_X)

        # bind the single click, release, and drag events to manage text box creation and deletion
        self.canvas.bind('<Button-1>', self.left_click)
        self.canvas.bind('<ButtonRelease-1>', self.release_click)
        self.canvas.bind('<B1-Motion>', self.click_drag)

        self.debug_button = ttk.Button(self.top, text='Debug', command=self.debug)
        self.save_button = ttk.Button(self.top, text='Save', command=self.write_output)

        self.draw_remarkable_contents()
        self.canvas.pack()
        self.debug_button.place(x=10,y=10)
        self.save_button.place(x=100,y=10)


    def draw_remarkable_contents(self):
        # draw page contents
        if self.canvas is not None:
            for layer in page.get_layers():
                for line in layer.get_lines():
                    if line._pen_nr != lines.Pen.ERASER:
                        x, y = line.get_point_coordinates_as_list()
                        xy_list = [item for pair in zip(x, y) for item in pair]
                        self.canvas.create_line(*xy_list, width=line.get_points()[0].width*1.25)
        else:
            print('Unable to draw remarkable contents, call create_windw() first')


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

            # record the start position
            self.start_coords = [event.x, event.y]

            # print('{} ({},{})'.format(text_status, event.x, event.y))
        elif self.text_status == TEXT_ACTIVE:
            # click event outside of text box, reset state
            self.text_status = TEXT_NONE
            self.save_text()



    def save_text(self):
        new_string = (self.text_box.get('1.0', 'end'))

        if len(new_string.strip()) > 0:
            # create a new label with the text
            lbl = ttk.Label(self.top, text=new_string, width=self.text_size[0], font=TEXTBOX_FONT,
                            wraplength=self.text_size[0]*TEXTBOX_WIDTH_DIVISOR, background="white")
            lbl.bind('<Button-3>', self.right_click)
            lbl.place(x=self.start_coords[0], y=self.start_coords[1])

            # store the text for later addition to rm notebook
            self.text_list.append(TextEntry(x=self.start_coords[0], y=self.start_coords[1],
                                            width=self.text_size[0], text=new_string))

        # destroy text box
        self.text_box.destroy()
        self.text_box = None


        # print('{} ({},{})'.format(text_status, event.x, event.y))


    def click_drag(self, event):
        # print('drag x = {}; y = {}'.format(event.x, event.y))

        if self.text_status == TEXT_START:
            # starting to drag
            self.text_status = TEXT_DRAGGING
            self.draw_rectangle((event.x, event.y))

            # print('{} ({},{})'.format(text_status, event.x, event.y))
        elif self.text_status == TEXT_DRAGGING:
            # continuing drag, update rectangle
            self.canvas.delete(self.outline_box)
            self.draw_rectangle((event.x, event.y))

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

                self.text_size[0] = int(abs(self.start_coords[0] - event.x) / TEXTBOX_WIDTH_DIVISOR)
                self.text_size[1] = int(abs(self.start_coords[1] - event.y) / TEXTBOX_HEIGHT_DIVISOR)

                self.start_coords[0] = min(self.start_coords[0], event.x)
                self.start_coords[1] = min(self.start_coords[1], event.y)

                # print('({},{}); ({},{})'.format(*self.start_coords, *self.text_size))

                # create text box and grab focus
                self.text_box = tkinter.Text(self.top, height=self.text_size[1], width=self.text_size[0], font=TEXTBOX_FONT)
                self.text_box.place(x=self.start_coords[0], y=self.start_coords[1])
                self.text_box.focus_set()
            else:
                # textbox too small
                self.text_status = TEXT_NONE

            # destroy rectangle
            self.canvas.delete(self.outline_box)
            # print('{} ({},{})'.format(text_status, event.x, event.y))


    def right_click(self, event):
        # if we clicked on a label then delete it
        if isinstance(event.widget, ttk.Label):
            if event.widget in self.labels:
                self.labels.remove(event.widget)
            event.widget.destroy()


    def write_output(self):
        if len(self.text_list) > 0:
            print('Adding string')
            for str in self.text_list:
                # add text to local rm file
                text_upload_sync.add_string(str.text, str.x, str.y, str.width*TEXTBOX_WIDTH_DIVISOR)

            print('Open item manager')
            im = model.item_manager.ItemManager()

            # connect to RM server
            print('Signing in')
            im.rm_client.sign_in()

            # upload to server
            print('Upload to server')
            text_upload_sync.upload(im)

            # sync with local remarkable
            print('Sync to local')
            text_upload_sync.sync(im)

            # clear local list
            self.text_list = []


    def debug(self):
        print('Entering debug mode')


if __name__ == '__main__':
    rema = RemarkableEditor()
    rema.create_window()
    rema.draw_remarkable_contents()
    rema.start_main_loop()
