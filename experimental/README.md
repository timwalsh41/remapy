## Description of files:

### Class files
* fonts.py: a class for importing truetype fonts and providing characters in bitmap or vector format for plotting and translation to rm lines format
* lines.py: a class to represent the components of a remarkable page, provides classes Page, Layer, Line, and Point for this purpose. Also provides an enum class Pen for the various remarkable pen types. Finally, provides a class LineParser to parse a remarkable lines file and return it as a Page object.
* synchronizer.py: a class to synchronize (copy) modified remarkable page files from the remapy local cache onto the remarkable via SSH/SFTP
* editor.py: a class to edit Remarkable notebook files in a standalone window

### Test files
* canvas_test.py: test of tkinter canvas for doing live editing of remarkable documents
* font_test.py: test of PIL ImageFont to load a truetype font file and get characters as a bitmap matrix of pixels
* freetype_test.py: a script to load a ttf font and process a character in vector format to plot in matplotlib
* glyph-vector-2.py: example script from freetype to render vector font characters
* lines_test.py: a script to open a remarkable page file, add lines/characters (with bitmap font), and save back out
* local_sync.py: a script that uses the Synchronizer class to copy any modified remarkable page files in the remapy local data cache onto the remarkable via SSH/SFTP
* paramiko_tests.py: a script to test out the SSH and SFTP functionality of the paramiko package
* text_upload_sync.py: a script that unifies lines_test.py, upload.py, and local_sync.py to modify a page file, upload it to the remarkable server, and sync it to the remarkable
* upload.py: a script that takes a locally modified rm page file and uploads to the remarkable cloud server
* vector_fonts_lines_test.py: a script that exercises the functionality in fonts.py and lines.py to get a rm lines representation of a character, and then extract and plot the character in matplotliib