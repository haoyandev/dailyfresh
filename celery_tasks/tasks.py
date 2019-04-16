# 使用celery
from celery import Celery
from django.conf import settings
from django.core.mail import send_mail
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dailyfresh.settings')
django.setup()
# 创建一个celery类的实例对象
app = Celery('celery_tasks.tasks', broker='redis://127.0.0.1:6379/0')


# 发送邮件函数
@app.task
def send_register_active_email(username, to_email, token):
    # 标题
    subject = '天天生鲜欢迎信息'
    # 内容
    message = ''
    # 发送人
    sender = settings.EMAIL_FROM
    # 收件人
    receiver = [to_email]

    # html内容
    html_message = '<h1>{},欢迎你成为天天生鲜注册会员</h1>请点击以下链接完成激活</br><a href="http://127.0.0.1:8000/user/active/{}">激活</a>'.format(
        username, token, token)
    print(html_message)
    send_mail(subject, message, sender, receiver, html_message=html_message)
    send_mail()
