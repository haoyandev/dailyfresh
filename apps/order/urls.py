from django.conf.urls import url
from order.views import OrderPlaceView, OrderCommitView, OrderPayView, OrderCheckView, OrderCommentView

urlpatterns = [
    url(r'^place$', OrderPlaceView.as_view(), name='place'),  # 创建订单
    url(r'^commit$', OrderCommitView.as_view(), name='commit'),  # 提交订单
    url(r'^pay$', OrderPayView.as_view(), name='pay'),  # 支付页面
    url(r'^check$', OrderCheckView.as_view(), name='check'),  # 支付结果查询
    url(r'^comment/(?P<order_id>\d+)$', OrderCommentView.as_view(), name='comment')

]
