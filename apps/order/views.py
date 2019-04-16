from django.shortcuts import render
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.core.urlresolvers import reverse
from django_redis import get_redis_connection
from django.views.generic import View
from django.conf import settings
from utils.Maxin import LoginRequiredMixin
from user.models import Address
from order.models import OrderInfo, OrderGoods
from goods.models import GoodsSKU
from django.db import transaction
from datetime import datetime
from alipay import AliPay
import time
import os

# Create your views here.


# order/place
class OrderPlaceView(LoginRequiredMixin, View):
    """创建订单"""

    @transaction.atomic
    def post(self, request):
        # 返回订单页面
        # 获取数据
        user = request.user
        sku_ids = request.POST.getlist('sku_ids')
        # 校验数据
        if not sku_ids:
            print(111)
            return redirect(reverse('cart:show'))
        # 业务处理
        con = get_redis_connection('default')
        key = 'cart_{}'.format(user.id)
        skus = []

        # 保存商品的总件数和总价格
        total_count = 0
        total_price = 0

        # 遍历sku_ids获取用户要购买的商品信息
        for sku_id in sku_ids:
            # 根据id获取商品对象
            sku = GoodsSKU.objects.get(id=sku_id)
            # 获取用户所购买的商品的数量
            count = con.hget(key, sku_id)
            # 计算价格
            amount = int(count) * sku.price
            # 动态赋予对象变量
            sku.count = count
            sku.amount = amount
            skus.append(sku)
            # 累计需要购买的商品的总件数和总价格
            total_count += int(count)
            total_price += amount

        transit = 10
        # 实际支付
        total_price += transit

        # 查询用户收货地址信息
        addrs = Address.objects.filter(user=user)

        # 编辑skus字符串
        sku_ids = ','.join(sku_ids)
        # 组织模板上下文
        content = {
            'skus': skus,
            'total_count': total_count,
            'total_price': total_price,
            'transit': transit,
            'addrs': addrs,
            'sku_ids': sku_ids
        }
        # 返回应答
        return render(request, 'place_order.html', content)


# order/commit
# 前端传来 收货地址(addr_id) 需要购买的商品(sku_ids) 支付方式(pay_method)
class OrderCommitView(View):
    """创建订单"""
    def post(self, request):
        # 创建订单
        # 获取数据
        addr_id = request.POST.get('addr_id')
        sku_ids = request.POST.get('sku_ids')
        pay_method = request.POST.get('pay_method')

        # 判断用户是否登录
        if not request.user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        else:
            user = request.user

        # 校验数据
        if not all([addr_id, sku_ids, pay_method]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        if pay_method not in OrderInfo.PAY_METHOD:
                return JsonResponse({'res': 2, 'errmsg': '不正确的支付方式'})
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '地址不正确'})
        # 业务处理
        # 组织参数
        # 新建订单号
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        # 商品的总数量和总价格
        total_count = 0
        total_price = 0
        # 运费
        transit_price = 10

        # 创建事务点
        sid = transaction.savepoint()
        try:
            # 创建订单
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user, addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price
                             )

            # 遍历用户需要买的商品id创建订单商品表
            con = get_redis_connection('default')
            sku_ids = sku_ids.split(',')
            key = 'cart_{}'.format(user.id)
            for sku_id in sku_ids:
                for i in range(3):
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except GoodsSKU.DoesNotExist:
                        # 回滚事务
                        transaction.savepoint_rollback(sid)
                        return JsonResponse({'res': 4, 'errmsg': '商品不存在'})
                    count = con.hget(key, sku_id)
                    count = int(count)
                    # 获取商品的原始库存
                    origin_stock = sku.stock

                    # 校验商品库存
                    if count > sku.stock:
                        transaction.savepoint_rollback(sid)
                        return JsonResponse({'res': 6, 'errmsg': '商品库量不足'})
                    # 乐观锁
                    new_stock = origin_stock - count
                    new_sales = sku.sales + count

                    # 更新商品的基本信息
                    res = GoodsSKU.objects.filter(id=sku_id, stock=origin_stock).update(stock=new_stock, sales=new_sales)

                    if res == 0:
                        if i == 2:
                            transaction.savepoint_rollback(sid)
                            return JsonResponse({'res': 8, 'errmsg': '下单失败2'})
                        continue

                    # 计算商品的小计
                    amount = count * sku.price

                    # 创建订单商品记录
                    order_goods = OrderGoods.objects.create(order=order,
                                                            sku=sku,
                                                            count=count,
                                                            price=amount
                                                            )
                    order_goods.save()

                    # 累计订单的商品数量和价格
                    total_price += amount
                    total_count += count
                    break

            # 更新订单信息
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(sid)
            print(e)
            return JsonResponse({'err': 7, 'errmsg': '下单失败1'})

        # 删除对应购物车记录
        con.hdel(key, *sku_ids)

        return JsonResponse({'res': 5, 'msg': '成功下单'})


# order/pay
# 前端ajax传来post请求 参数(order_id)
class OrderPayView(View):
    """支付页面"""
    def post(self, request):
        # 对接支付宝接口
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接收参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})

        try:
            # 校验该订单是不是当前用户的
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)

        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '无效订单号'})

        # 业务处理 使用python sdk调用支付宝接口
        alipay = AliPay(
            appid="2016092500595178",  # 应用id
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False True访问沙箱
        )

        # 调用支付接口
        # 电脑网站支付，需要跳转到https://openapi.alipay.com/gateway.do? + order_string
        total_amount = order.total_price + order.transit_price
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,  # 订单号
            total_amount=str(total_amount),  # 总金额
            subject='天天生鲜{}'.format(order_id),  # 标题
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )

        # 返回应答 dev是沙箱开发url
        pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res': 3, 'pay_url': pay_url})


class OrderCheckView(View):
    """支付结果查询"""
    def post(self, request):
        # 返回支付结果
        # 对接支付宝接口
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接收参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})

        try:
            # 校验该订单是不是当前用户的
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)

        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '无效订单号'})

        while True:
            # 业务处理 使用python sdk调用支付宝接口
            alipay = AliPay(
                appid="2016092500595178",  # 应用id
                app_notify_url=None,  # 默认回调url
                app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
                # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
                alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
                sign_type="RSA2",  # RSA 或者 RSA2
                debug=True  # 默认False True访问沙箱
            )

            # 调用查询接口
            response = alipay.api_alipay_trade_query(order_id)
            code = response.code
            print(code)
            if code == '1000' and response.get('trade_stutas') == 'TRADE_SUCCESS':
                # 修改订单信息
                trade_no = response.get('trade_no')
                order.trade_no = trade_no
                order.trade_status = 4
                order.save()
                return JsonResponse({'res': 3, 'msg': '支付成功'})
            elif code == '1000' and response.get('trade_stutas') == 'WAIT_BUYER_PAY':
                time.sleep(5)
                continue
            else:
                return JsonResponse({'res': 4, 'errmsg': '支付失败'})


class OrderCommentView(LoginRequiredMixin, View):
    """订单评论"""
    def get(self, request, order_id):
        # 返回评论页面
        # 校验订单
        user = request.user
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          order_status=4)
        except OrderInfo.DoesNotExist:
            # 无效订单
            return redirect(reverse('user:order', kwargs={'page': 1}))
        # 查询该订单每个商品信息
        skus = OrderGoods.objects.filter(order=order)

        # 遍历每个商品计算小计
        for sku in skus:
            amount = sku.count * sku.count
            sku.amount = amount

        order.skus = skus

        # 组织参数
        context = {
            'order': order
        }

        return render(request, 'order_comment.html', context)

    def post(self, request, order_id):
        # 处理评论
        print(request.POST)

        # 获取数据
        order_id = request.POST.get('order_id')
        goods_count = request.POST.get('goods_count')

        # 校验数据
        if not order_id:
            # 数据不完整
            return redirect(reverse('user:order', kwargs={'page': 1}))

        try:
            order = OrderInfo.objects.get(order_id=order_id)
        except OrderInfo.DoesNotExist:
            # 无效订单
            return redirect(reverse('user:order', kwargs={'page': 1}))

        # 业务处理
        # 遍历订单商品中的评论
        for i in range(1, int(goods_count)+1):
            sku_id = request.POST.get('comment_{}'.format(i))
            content = request.POST.get('content_{}'.format(sku_id))
            try:
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                # 商品不存在
                continue
            try:
                order_goods = OrderGoods.objects.get(order=order, sku=sku)
            except OrderGoods.DoesNotExist:
                # 订单商品不存在
                continue

            # 添加评论
            order_goods.comment = content
            order_goods.save()
            # 更新订单状态
            order.order_status = 5
            order.save()
        # 返回应答
        return redirect(reverse('user:order', kwargs={'page': 1}))

