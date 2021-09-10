import paramiko
import json
import io
import model.document

# Wareham
REMARKABLE_IP = '192.168.1.162'

# Andover
# REMARKABLE_IP = '192.168.39.150'

# Password - from Settings -> Help > Copyrights and Licenses
REMARKABLE_PASSWORD = '88D6RNPEL9'

# root folder for remarkable tree
ROOT_FOLDER = '/home/root/.local/share/remarkable/xochitl/'

HOST_KEYS_FILE = '/home/tim/.ssh/known_hosts'

class Synchronizer:
    def __init__(self, ip=None, password=None):
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
                self.client.connect(ip, username='root', password=password)
                self.sftp_client = self.client.open_sftp()
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
        return self._connected


    def local_sync(self, item):
        if item.type == model.document.TYPE_NOTEBOOK:

            metadata_remarkable_path = ROOT_FOLDER + item.id() + '.metadata'
            content_remarkable_path = ROOT_FOLDER + item.id() + '.content'

            metadata_file = self.sftp_client.open(metadata_remarkable_path, mode='r')
            data = metadata_file.read().decode('utf-8')
            metadata_file.close()
            metadata_json = json.loads(data)

            print('{} {}; RM version = {}; PC version = {}'.format(item.id(), item.metadata['VissibleName'], metadata_json['version'], item.metadata['Version']))

            if item.metadata['Version'] > metadata_json['version']:
                # update version in metadata
                metadata_json['version'] = item.metadata['Version']

                # now write this out to the remarkable
                metadata_io = io.StringIO(json.dumps(metadata_json, indent=4))
                self.sftp_client.putfo(fl=metadata_io, remotepath=metadata_remarkable_path)

                # grab content file to get page IDs
                content_file = self.sftp_client.open(content_remarkable_path, mode='r')
                data  = content_file.read().decode('utf-8')
                content_file.close()
                content_json = json.loads(data)

                for idx,page in enumerate(content_json['pages']):
                    print('Updating page {} - {}'.format(idx, page))

                    # source pagefile is the .rm page path on the local machine
                    source_pagefile = item.path + '/' + item.id() + '/' f'{idx}.rm'

                    # source page metadata file from the local machine
                    source_metadatafile = item.path + '/' + item.id() + '/' f'{idx}-metadata.json'

                    # destination pagefile is the .rm page path on the remarkable
                    destination_pagefile = ROOT_FOLDER + item.id() + '/' + f'{page}.rm'

                    # destination metadata file on the remarkable
                    destination_metadatafile = ROOT_FOLDER + item.id() + '/' + f'{page}-metadata.json'

                    # transfer local page and metadata files to the remarkable
                    self.sftp_client.put(localpath=source_pagefile, remotepath=destination_pagefile)
                    self.sftp_client.put(localpath=source_metadatafile, remotepath=destination_metadatafile)






