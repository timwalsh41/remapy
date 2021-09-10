import paramiko
import time
import json

# Wareham
# remarkable_IP = '192.168.1.162'

# Andover
remarkable_IP = '192.168.39.149'

remarkable_password = '88D6RNPEL9'

# root folder for remarkable tree
root_folder = '/home/root/.local/share/remarkable/xochitl/'

test_file = 'df1b8fdf-f368-4448-9ac9-b9f8c3ab0b4b.metadata'

connected = False
client = paramiko.SSHClient()
client.load_host_keys('/home/tim/.ssh/known_hosts')
try:
    client.connect(remarkable_IP, username='root', password=remarkable_password)
    connected = True
except paramiko.ssh_exception.AuthenticationException:
    print('Authentication failed')
except paramiko.ssh_exception.NoValidConnectionsError:
    print('Connection failed to {} port 22'.format(remarkable_IP))

#stdin, stdout, stderr = client.exec_command(f'cd {root_folder}')
#print(stdout.read().decode('utf-8'))
#print(stderr.read().decode('utf-8'))

#stdin.write('ls -la')

# stdin, stdout, stderr = client.exec_command('ls -lah')
# stdin, stdout, stderr = client.exec_command('/bin/sh')
#stdin.write('pwd\n')
# print(stdout.read().decode('utf-8'))

# stdin.close()
# stdout.close()
# stderr.close()

if connected:
    shell = client.invoke_shell()
    time.sleep(0.1)

    while shell.recv_ready():
        data = shell.recv(128)
        # print(data)
        time.sleep(0.05)

    #print('Switching folder')
    #shell.send(f'cd {root_folder}\n')
    #shell.send('ls -la\n')
    #time.sleep(0.1)

    #while shell.recv_ready():
    #    data = shell.recv(128)
    #    print(data)
    #    time.sleep(0.05)

    shell.send(f'cat {root_folder + test_file}\n')
    # shell.send('echo 0')
    time.sleep(0.25)

    shell_ret = ''
    while shell.recv_ready():
        shell_ret = shell_ret + shell.recv(128).decode('utf-8')
        #print(data.decode('utf-8'))
        time.sleep(0.25)

    idx1 = shell_ret.find('{')
    idx2 = shell_ret.rindex('}')

    print(shell_ret[idx1:idx2+1])

    j = json.loads(shell_ret[idx1:idx2+1])

    print(f'\nVersion = {j["version"]}')

    sftp_client = client.open_sftp()
    metadata_file = sftp_client.open(root_folder + test_file, mode='r')

    data = metadata_file.read().decode('utf-8')
    metadata_file.close()

    data_json = json.loads(data)

    print(data_json['version'])

    out_file = sftp_client.open('/home/root/test.txt', mode='w')
    out_file.write('This is a test\r\n')
    out_file.close()

    sftp_client.close()
    shell.close()
    client.close()


