from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client
from django.conf import settings

class FDFSStorage(Storage):
    """自定义存储类"""
    
    def __init__(self, client_conf=None, base_url=None):
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF
        self.client_conf = client_conf

        if base_url is None:
            base_url = settings.FDFS_URL
        self.base_url = base_url
            
    def _open(self, name, mode='rb'):
        """打开文件"""
        pass

    def _save(self, name, content):
        # name 你选择上传文件的名字
        # content 包含你上传内容的file对象

        # 创建fdfs_client对象
        client = Fdfs_client(self.client_conf)

        # 上传文件
        # content.read() 读取文件内容
        res = client.upload_by_buffer(content.read())

        # 判断是否成功
        if res.get('Status') != 'Upload successed.':
            raise Exception('上传fdfs文件失败')

        filename = res.get('Remote file_id')
        return filename

    def exists(self, name):
        return False

    def url(self, name):
        return self.base_url + '/' + name


