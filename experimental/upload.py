# upload modified RM document to server
#
# Steps:
# 1. Build new output file with lines_test.py
# 2. Copy output file ("test.rm" is the default name) to replace the corresponding page file in the
#    remapy data folder
# 3. Build the zip file manually (with the updated .rm file) in the root folder for the given document
# 4. Run this script to upload it to the server

import model.item_manager

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

def upload_request(im, id, metadata):
    response = im.rm_client._request("PUT", "/document-storage/json/2/upload/request",
                             body=[{
                                 "ID": id,
                                 "Type": "DocumentType",
                                 "Version": metadata["Version"]
                             }])

    return response

id = '0e6ceff0-3137-4dcc-8672-ee63c32621e1'

# open item manager
im = model.item_manager.ItemManager()

# connect to RM server
im.rm_client.sign_in()
root = im.get_root()

item = im.get_item(id=id)

# update document version in metadata
item.metadata["Version"] += 1
print('New item version is {}'.format(item.metadata["Version"]))

# update the local metadata
item._write_metadata()

# build zip file
mf = read_zip_file(id, item.path)

if mf is not None:
    response = upload_request(im, id, item.metadata)

    if response.ok:
        BlobURL = response.json()[0].get('BlobURLPut')

        response = im.rm_client._request('PUT', BlobURL, data=mf)
        retval = im.rm_client.update_metadata(item.metadata)
        print(response.ok)

pass