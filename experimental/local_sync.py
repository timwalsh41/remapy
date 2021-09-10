import synchronizer
from model.item_manager import ItemManager

im = ItemManager()

im.rm_client.sign_in()
root = im.get_root()

syncro = synchronizer.Synchronizer(ip=synchronizer.REMARKABLE_IP, password=synchronizer.REMARKABLE_PASSWORD)
syncro.connect_ssh()

if syncro.is_connected():
    im.traverse_tree(fun=syncro.local_sync, document=True, collection=False)

syncro.disconnect()



