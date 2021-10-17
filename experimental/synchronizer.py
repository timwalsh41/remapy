import paramiko
import json
import io
import model.document
import hashlib

# Wareham
# REMARKABLE_IP = '192.168.1.162'

# Andover
REMARKABLE_IP = '192.168.39.149'

# Password - from Settings -> Help > Copyrights and Licenses
REMARKABLE_PASSWORD = '88D6RNPEL9'

# root folder for remarkable tree
RM_ROOT_FOLDER = '/home/root/.local/share/remarkable/xochitl/'

# TODO: find add known hosts file to settings
HOST_KEYS_FILE = '/home/tim/.ssh/known_hosts'

class Synchronizer:
    def __init__(self, ip=REMARKABLE_IP, password=REMARKABLE_PASSWORD):
        # configure paramiko ssh client
        self.client = paramiko.SSHClient()
        self.client.load_host_keys(HOST_KEYS_FILE)

        # IP address and password for ssh connection to remarkable
        self.ip = ip
        self.password = password

        # status flag for SSH connection
        self._connected = False

        # placeholder for sftp client
        self.sftp_client = None


    def connect_ssh(self, ip=None, password=None):
        if ip is None:
            ip = self.ip

        if password is None:
            password = self.password

        if password is not None and ip is not None:
            try:
                self.client.connect(ip, username='root', password=password, timeout=30)
                self.transport = self.client.get_transport()
                self.sftp_client = self.client.open_sftp()

                # we'll set the sftp timeout to 60 seconds; if the Remarkable goes to sleep during
                # local sync we want the process to timeout in a reasonable amount of time
                self.sftp_client.get_channel().settimeout(60)
                self._connected = True

            except paramiko.ssh_exception.AuthenticationException:
                print('Unable to connect to remarkable - authentication error')

            except paramiko.ssh_exception.NoValidConnectionsError:
                print('Unable to connect to connect to remarkable on {} port 22'.format(self.ip))

            except paramiko.ssh_exception.SSHException:
                print('Unable to connect to remarkable on {} - server is not in known_hosts'.format(self.ip))

        else:
            print('Unable to connect to remarkable - invalid IP address and/or password')


    def disconnect(self):
        if self._connected:
            self.sftp_client.close()
            self.client.close()
            self._connected = False


    def is_connected(self):
        return self._connected and self.transport.is_active()


    # Local sync function to copy files from local repo to Remarkable.
    # This version works by comparing page files (by calculating an md5 checksum) between the
    # local repo and the Remarkable. Wherever there is a mismatch, we assume the latest version
    # is in the local repo and copy the page to the Remarkable.
    def local_sync_md5(self, item):
        if not self.is_connected():
            print('No SSH connection - aborting sync effort')
            return

        if item.type == model.document.TYPE_NOTEBOOK:
            print('{}'.format(item.metadata['VissibleName']))

            # grab content file to get page IDs
            rm_content_path = RM_ROOT_FOLDER + item.id() + '.content'

            if not self.is_connected():
                print('Lost SSH connection')
                return

            # attempt to read content file from Remarkable, we will get an exception if the
            # process times out
            try:
                content_file = self.sftp_client.open(rm_content_path, mode='r')
                data = content_file.read().decode('utf-8')
                content_file.close()
            except:
                print('Unable to access remote file {}'.format(rm_content_path))
                return

            rm_content_json = json.loads(data)

            # loop over each page in the notebook, comparing the local version and the version
            # on the Remarkable
            for idx, page in enumerate(rm_content_json['pages']):
                # path to the corresponding page in the local repo
                local_pagefile_path = item.path + '/' + item.id() + '/' f'{idx}.rm'

                print('\tProcessing page {}'.format(idx))

                # read in local pagefile
                try:
                    with open(local_pagefile_path, 'rb') as f:
                        local_pagefile_data = f.read()
                except:
                    print('Unable to sync page {}-{}'.format(item.metadata['VissibleName'], idx))
                    continue

                # calculate md5 digest for local pagefile
                local_pagefile_md5 = hashlib.md5(local_pagefile_data).hexdigest()

                # path to the page file on the remarkable
                rm_pagefile_path = RM_ROOT_FOLDER + item.id() + '/' + f'{page}.rm'

                if not self.is_connected():
                    print('Lost SSH connection')
                    return

                # read in the page data from the remarkable
                try:
                    content_file = self.sftp_client.open(rm_pagefile_path, mode='rb')
                    rm_pagefile_data = content_file.read()
                    content_file.close()
                except:
                    print('Unable to access remote file {}'.format(rm_pagefile_path))
                    continue

                # calculate md5 digest for the remarkable pagefile
                rm_pagefile_md5 = hashlib.md5(rm_pagefile_data).hexdigest()

                if local_pagefile_md5 != rm_pagefile_md5:
                    print('\tCopying to Remarkable: {}.{}.{}'.format(item.id(), idx, page))
                    if not self.is_connected():
                        print('Lost SSH connection')
                        return

                    try:
                        self.sftp_client.put(localpath=local_pagefile_path, remotepath=rm_pagefile_path)
                    except:
                        print('Unable to copy into remote file {}'.format(rm_pagefile_path))
                # else:
                #    print('\tMatch: {}.{}.{}'.format(item.id(), idx, page))


    # Local sync function - copy page files from local repo to Remarkable
    # In this version of the function, files will be copied when the version on the
    # local repo is later than the version on the Remarkable
    # Note that Remarkable seems to update the version on the Remarkable whenever a file
    # is uploaded to the cloud (even from RemaPy), so this method would only work
    # when editing on a local machine and loading to the Remarkable before it's uploaded
    # to the cloud. Use local_sync_md5 instead.
    def local_sync(self, item):
        if item.type == model.document.TYPE_NOTEBOOK:

            rm_metadata_path = RM_ROOT_FOLDER + item.id() + '.metadata'
            rm_content_path = RM_ROOT_FOLDER + item.id() + '.content'

            metadata_file = self.sftp_client.open(rm_metadata_path, mode='r')
            data = metadata_file.read().decode('utf-8')
            metadata_file.close()
            rm_metadata_json = json.loads(data)

            print('{} {}; RM version = {}; PC version = {}'.format(item.id(), item.metadata['VissibleName'], metadata_json['version'], item.metadata['Version']))

            if item.metadata['Version'] > rm_metadata_json['version']:
                # update version in metadata
                rm_metadata_json['version'] = item.metadata['Version']

                # now write this out to the remarkable
                metadata_io = io.StringIO(json.dumps(rm_metadata_json, indent=4))
                self.sftp_client.putfo(fl=metadata_io, remotepath=rm_metadata_path)

                # grab content file to get page IDs
                content_file = self.sftp_client.open(rm_content_path, mode='r')
                data  = content_file.read().decode('utf-8')
                content_file.close()
                rm_content_json = json.loads(data)

                for idx,page in enumerate(rm_content_json['pages']):
                    print('Updating page {} - {}'.format(idx, page))

                    # source pagefile is the .rm page path on the local machine
                    source_pagefile = item.path + '/' + item.id() + '/' f'{idx}.rm'

                    # source page metadata file from the local machine
                    source_metadatafile = item.path + '/' + item.id() + '/' f'{idx}-metadata.json'

                    # destination pagefile is the .rm page path on the remarkable
                    destination_pagefile = RM_ROOT_FOLDER + item.id() + '/' + f'{page}.rm'

                    # destination metadata file on the remarkable
                    destination_metadatafile = RM_ROOT_FOLDER + item.id() + '/' + f'{page}-metadata.json'

                    # transfer local page and metadata files to the remarkable
                    self.sftp_client.put(localpath=source_pagefile, remotepath=destination_pagefile)
                    self.sftp_client.put(localpath=source_metadatafile, remotepath=destination_metadatafile)






