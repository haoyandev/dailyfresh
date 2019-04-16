from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client


class FDFSStorage(Storage):
    """自定义存储类"""
    def _open(self, name, mode='rb'):
        """打开文件"""
        pass

    def _save(self, name, content):
        # name 你选择上传文件的名字
        # content 包含你上传内容的file对象

        # 创建fdfs_client对象
        client = Fdfs_client('./utils/fdfs/client.conf')

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
        return 'http://192.168.88.101:8888/'+name


