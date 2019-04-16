from django.conf.urls import url
from apps.user.views import RegisterView, ActiveView, LoginView, UserInfoView, UserOrderView, AddressView, LogoutView

urlpatterns = [
    url(r'^register$', RegisterView.as_view(), name='register'),  # 注册
    url(r'^active/(?P<token>.*)', ActiveView.as_view(), name='active'),  # 用户激活
    url(r'^login$', LoginView.as_view(), name='login'),  # 登录
    url(r'^logout$', LogoutView.as_view(), name='logout'),  # 退出
    url(r'^$', UserInfoView.as_view(), name='info'),  # 用户信息
    url(r'^order/(?P<page>\d+)$', UserOrderView.as_view(), name='order'),  # 用户订单
    url(r'^address$', AddressView.as_view(), name='address'),  # 用户地址




]
