import os
import uuid
import shutil
import zipfile
from zipfile import ZipFile
from pathlib import Path
import datetime
from time import gmtime, strftime
import json
import experimental.lines as lines


from api.remarkable_client import RemarkableClient
from utils.helper import Singleton
import model.render as render
import model.item
from model.item import Item
from model.collection import Collection
import utils.config as cfg


# Document type states
TYPE_UNKNOWN = 0       # If it is only online we don't know the state
TYPE_NOTEBOOK = 1
TYPE_PDF = 2
TYPE_EPUB = 3

# Synced with cloud states
STATE_NOT_SYNCED = 200
STATE_OUT_OF_SYNC = 201



class Document(Item):
    """ This class represents a rm document i.e. pdf, epub or notebook
    """

    #
    # CTOR
    #
    def __init__(self, metadata, parent: Collection):
        super(Document, self).__init__(metadata, parent)

        # Remarkable tablet paths
        self.path_zip = "%s.zip" % self.path
        self.path_rm_files = "%s/%s" % (self.path, self.id())
        self.path_content_file = "%s/%s.content" % (self.path, self.id())

        # RemaPy paths
        self.path_annotated_pdf = self._get_path_annotated_pdf()
        self.path_oap_pdf = self._get_path_oap_pdf()
        self.path_original_pdf = "%s/%s.pdf" % (self.path, self.id())
        self.path_original_epub = "%s/%s.epub" % (self.path, self.id())
        self.path_highlighter = "%s/%s.highlights/" % (self.path, self.id())

        # Other props
        self.download_url = None
        self.blob_url = None
        self.state = None       # Synced, out of sync etc.
        self.type = None        # Unknown (not downloaded yet), pdf, epub or notebook

        # Set correct state of document
        self._update_state()


    #
    # Getter and setter
    #
    def _get_path_annotated_pdf(self):
        return "%s/%s.pdf" % (self.path_remapy, self.name().replace("/", "."))

    def _get_path_oap_pdf(self):
        return "%s/%s_oap.pdf" % (self.path_remapy, self.name().replace("/", "."))


    def current_page(self):
        return self._meta_value("CurrentPage", 0) + 1


    def is_parent_of(self, item):
        return False


    def full_name(self):
        return "%s/%s" % (self.parent().full_name(), self.name())


    def ann_or_orig_file(self):
        if os.path.exists(self.path_annotated_pdf):
            return self.path_annotated_pdf

        return self.orig_file()


    def is_landscape(self):
        with open(self.path_content_file, "r") as f:
            content_file = json.load(f)
            orientation = content_file["orientation"]
        return orientation.lower() == "landscape"


    def get_pages(self):
        with open(self.path_content_file, "r") as f:
            content_file = json.load(f)
            pages = content_file["pages"]

        return pages


    def rename(self, new_name):

        self.path_oap_pdf
        super(Document, self).rename(new_name)

        try:
            old = self.path_annotated_pdf
            self.path_annotated_pdf = self._get_path_annotated_pdf()
            os.rename(old, self.path_annotated_pdf)
        except:
            pass

        try:
            old = self.path_oap_pdf
            self.path_oap_pdf = self._get_path_oap_pdf()
            os.rename(old, self.path_oap_pdf)
        except:
            pass


    def oap_file(self):
        """ Returns Only Annotated Pages of the pdf file. For notebooks
            this is every page...
        """
        # For notebooks this not really exists. Therefore
        # we return the annotated pdf
        if self.type == TYPE_NOTEBOOK:
            return self.path_annotated_pdf

        if os.path.exists(self.path_oap_pdf):
            return self.path_oap_pdf

        return None


    def orig_file(self):
        if self.type == TYPE_EPUB:
            return self.path_original_epub
        if self.type == TYPE_NOTEBOOK:
            return self.path_annotated_pdf
        else:
            return self.path_original_pdf


    #
    # Functions
    #
    def delete_local(self):
        if os.path.exists(self.path):
            shutil.rmtree(self.path)
        self._update_state()


    def delete(self):
        ok = self.rm_client.delete_item(self.id(), self.version())

        if ok:
            self.state = model.item.STATE_DELETED
            self._update_state_listener()
        return ok


    def sync(self):
        if self.state == model.item.STATE_SYNCING:
            return

        self.state = model.item.STATE_SYNCING
        self._update_state_listener()

        self._download_raw()
        self._write_remapy_file()
        self._update_state(inform_listener=False)

        annotations_exist = os.path.exists(self.path_rm_files)

        if self.type == TYPE_NOTEBOOK and annotations_exist:
            render.notebook(
                self.path,
                self.id(),
                self.path_annotated_pdf,
                self.is_landscape(),
                path_templates=cfg.get("general.templates"))

        else:
            if annotations_exist:
                # Also for epubs a pdf file exists which we can annotate :)
                # We will then show the pdf rather than the epub...
                render.pdf(
                    self.path_rm_files,
                    self.path_highlighter,
                    self.get_pages(),
                    self.path_original_pdf,
                    self.path_annotated_pdf,
                    self.path_oap_pdf)

        self._update_state()
        self.parent().sync()


    def _download_raw(self, path=None):
        path = self.path if path == None else path

        if self.blob_url == None:
            self.blob_url = self.rm_client.get_item(self.id())["BlobURLGet"]

        raw_file = self.rm_client.get_raw_file(self.blob_url)
        with open(self.path_zip, "wb") as out:
            out.write(raw_file)

        if self.type != TYPE_NOTEBOOK:
            # for all types other than notebook, we just download and extract (no merging)
            if os.path.exists(path):
                shutil.rmtree(path)

            # extract zip file into folder
            with zipfile.ZipFile(self.path_zip, "r") as zip_ref:
                zip_ref.extractall(path)

            # Update state
            self._update_state(inform_listener=False)

            return

        if os.path.exists(path):
            # grab the .content file to get the page ids
            local_content_file = open(os.path.join(path, '{}.content'.format(self.id())), 'r')
            local_content_file_data = local_content_file.read()
            local_content_json = json.loads(local_content_file_data)

            # create a copy of the page data folder
            shutil.copytree(os.path.join(path, self.id()), os.path.join(path, 'page_data_backup'))

            # now remove unneeded files
            os.remove(os.path.join(path, '{}.content'.format(self.id())))
            os.remove(os.path.join(path, '{}.pagedata'.format(self.id())))
            shutil.rmtree(os.path.join(path, self.id()))
            shutil.rmtree(os.path.join(path, '.remapy'))

            # create folder for page files
            os.makedirs(os.path.join(path, self.id()))

        else:
            # no local content to merge, just extract zip file into folder
            with zipfile.ZipFile(self.path_zip, "r") as zip_ref:
                zip_ref.extractall(path)

            # Update state
            self._update_state(inform_listener=False)

            return

        # open up zip file and merge page by page
        with zipfile.ZipFile(self.path_zip, "r") as zip_ref:
            # get content file data from zip file
            remote_content_file = zip_ref.open(name='{}.content'.format(self.id()), mode='r')
            remote_content_file_data = remote_content_file.read()
            remote_content_json = json.loads(remote_content_file_data)

            # loop through page IDs in remote file
            for remote_idx, remote_page_id in enumerate(remote_content_json['pages']):
                # find corresponding page in local file
                local_match = False
                for local_idx, local_page_id in enumerate(local_content_json['pages']):
                    if local_page_id == remote_page_id:
                        local_match = True
                        break

                if local_match:
                    # we have found the corresponding page, load both pages and merge
                    local_page = lines.LineParser(os.path.join(path, 'page_data_backup', '{}.rm'.format(local_idx)))
                    local_page.read_rm_file()
                    local_page_data, local_page_md5 = local_page.parse_rm_data(calculate_MD5=True)

                    remote_page = lines.LineParser()
                    remote_page.read_rm_data_from_zip(self.id(), zip_ref, remote_idx)
                    remote_page_data, remote_page_md5 = remote_page.parse_rm_data(calculate_MD5=True)

                    # run merge on the local and remote pages
                    merged_page = lines.merge_pages(local_page_data, local_page_md5, remote_page_data,
                                                    remote_page_md5)

                    # save merged page out to data folder
                    merged_page.write_output_file(os.path.join(path, self.id(), '{}.rm'.format(remote_idx)))

                    # create page metadata json file
                    merged_page.write_metadata_json_file(os.path.join(path, self.id(), '{}-metadata.json'.format(remote_idx)))
                else:
                    # no match, take the remote file as-is and extract into the data folder
                    zip_ref.extract('{}/{}.rm'.format(self.id(), remote_idx))
                    zip_ref.extract('{}/{}-metadata.json'.format(self.id(), remote_idx))

            # take pagedata and content files as-is from server
            # TODO: need to create pagedata/content file from merged document
            # for new we can't create/insert/delete pages with remapy, so we are safe to take the version from
            # the server
            zip_ref.extract('{}.pagedata'.format(self.id()), path)
            zip_ref.extract('{}.content'.format(self.id()), path)

        # remove unneeded files
        os.remove(self.path_zip)
        shutil.rmtree(os.path.join(path, 'page_data_backup'))

        # Update state
        self._update_state(inform_listener=False)


    def update_state(self):
        self._update_state(inform_listener=True)


    def _update_state(self, inform_listener=True):

        # Not synced
        if not os.path.exists(self.path_metadata_local):
            self.type = TYPE_UNKNOWN
            self.state = STATE_NOT_SYNCED

        # If synced get file type
        else:
            with open(self.path_metadata_local, encoding='utf-8') as f:
                local_metadata = json.loads(f.read())

            self.state = model.item.STATE_SYNCED if local_metadata["Version"] == self.version() else STATE_OUT_OF_SYNC
            is_epub = os.path.exists(self.path_original_epub)
            is_pdf = not is_epub and os.path.exists(self.path_original_pdf)

            if is_epub:
                self.type = TYPE_EPUB
            elif is_pdf:
                self.type = TYPE_PDF
            else:
                self.type = TYPE_NOTEBOOK

        # Inform listener if needed
        if not inform_listener:
            return

        self._update_state_listener()


    def create_backup(self, backup_path):

        backup_path = "%s/%s" % (backup_path, self.parent().full_name())
        Path(backup_path).mkdir(parents=True, exist_ok=True)

        file_to_backup = self.ann_or_orig_file()
        extension = os.path.splitext(file_to_backup)[1]
        file_name = self.name().replace("/", ".") + extension
        shutil.copyfile(file_to_backup, backup_path + "/" + file_name)
