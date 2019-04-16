from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.contrib.auth import authenticate, login, logout
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from django.views.generic import View
from user.models import User, Address
from goods.models import GoodsSKU
from order.models import OrderInfo, OrderGoods
from django.conf import settings
from django_redis import get_redis_connection
from celery_tasks.tasks import send_register_active_email
from utils.Maxin import LoginRequiredMixin
import re
# create your views here.


# /user/register
class RegisterView(View):
    """注册"""
    def get(self, request):
        """注册页面"""
        return render(request, 'register.html')

    def post(self, request):
        # 接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        cpassword = request.POST.get('cpwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 验证数据
        if not all([username, password, cpassword, email, allow]):
            return render(request, 'register.html', {'errmsg': '数据不全'})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})

        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if not password == cpassword:
            return render(request, 'register.html', {'errmsg': '两次密码不相同'})
        try:
            # 只返回一条数据 如果不存在则报错(doesnotexist)
            User.objects.get(username=username)
        except User.DoesNotExist:
            # 抛出异常 则用户不存在
            user = None
        else:
            return render(request, 'register.html', {'errmsg': '该用户已存在'})

        # 业务处理
        user = User.objects.create_user(username=username, password=password, email=email)
        # django自带的用户模型是默认激活的
        user.is_active = False
        user.save()

        # 发送加密激活邮件 包含激活链接http://127.0.0.1:8000/active
        # 激活链接要包含身份信息 并且要把身份信息进行加密
        # 加密用户身份信息 生成token
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info)
        token = token.decode()

        # 发送邮件
        send_register_active_email.delay(username, email, token)
        # 返回应答
        # response.set_cookies('username', username, max_age=17*24*3600)
        return redirect(reverse('goods:index'))


# /user/active
class ActiveView(View):
    """激活用户"""
    def get(self, request, token):
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            # 解密用户身份信息
            token = serializer.loads(token)
        except SignatureExpired as e:
            # 产生异常 激活超时
            return HttpResponse('激活已失效')
        else:
            # 取出用户id 并且激活
            user_id = token.get('confirm')
            user = User.objects.get(id=user_id)
            user.is_active = True
            user.save()
            return redirect(reverse('goods:index'))


# /user/login
class LoginView(View):
    """登录"""
    def get(self, request):
        # 返回登录页面
        # 判断是否记住用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request, 'login.html', {'username': username, 'checked': checked})

    def post(self, request):
        # 接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        # 验证数据
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': '数据不完整'})

        # 业务处理
        user = authenticate(username=username, password=password)
        if user is not None:
            # 用户或密码正确
            if user.is_active:
                # 用户已激活
                login(request, user)
                # 当用户名密码都正确下 判断要跳转的下一个页面
                next_url = request.GET.get('next', reverse('goods:index'))
                response = redirect(next_url)
                # 判断是否记住用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    # 记住用户名
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    # 不记住用户名
                    response.delete_cookie('username')

            else:
                # 用户未激活
                return HttpResponse('该用户未激活')

        else:
            # 用户或密码不正确
            return render(request, 'login.html', {'errmsg': '用户或密码不正确'})

        return response


# /user/logout
class LogoutView(View):
    """退出登录"""
    def get(self, request):
        logout(request)
        return redirect(reverse('goods:index'))


# /user
class UserInfoView(LoginRequiredMixin, View):
    # 用户信息

    # django框架会把request.user也传到模板中 模板中使用user即可
    def get(self, request):
        # 用户基本信息
        page = 'user'
        user = request.user
        address = Address.objects.get_default_address(user=user)

        # 用户历史浏览记录
        con = get_redis_connection('default')
        history_key = 'history_{}'.format(user.id)
        # 获取用户最近浏览的5条商品id信息
        goods_ids = con.lrange(history_key, 0 ,4)
        # 遍历商品id获取商品对象
        goods_list = []
        for id in goods_ids:
            good = GoodsSKU.objects.get(id=id)
            goods_list.append(good)
        context = {'page': page,
                   'address': address,
                   'goods_list': goods_list
                   }

        return render(request, 'user_center_info.html', context)


# /user/address
class AddressView(LoginRequiredMixin, View):
    # 用户地址

    def get(self, request):
        page = 'address'
        # 获取默认地址
        user = request.user
        address = Address.objects.get_default_address(user=user)
        # 返回用户地址页面
        return render(request, 'user_center_site.html', {'page': 'address', 'address': address})

    def post(self, request):
        # 新增用户地址
        # 获取数据
        receiver = request.POST.get('receiver')
        address = request.POST.get('address')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        # 校验数据完整性
        if not all([receiver, address, phone]):
            return render(request, 'user_center_site.html', {'errmsg': '数据不完整'})

        # 校验手机合法性
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$', phone):
            return render(request, 'user_center_site.html', {'errmsg': '手机号码不正确'})

        # 判断是否有默认地址
        user = request.user
        if Address.objects.get_default_address(user=user):
            is_default = True
        else:
            is_default = False

        new_address = Address.objects.create(user=user,
                                             receiver=receiver,
                                             addr=address,
                                             zip_code=zip_code,
                                             phone=phone,
                                             is_default=is_default)
        new_address.save()
        return redirect(reverse('user:address'))


# /user/order
class UserOrderView(LoginRequiredMixin, View):
    """用户订单"""
    def get(self, request, page):
        # 显示用的订单
        user = request.user

        # 查询用户所有的订单记录
        orders = OrderInfo.objects.filter(user=user)

        if orders:
            # 遍历所有订单查询相关商品
            for order in orders:
                order_skus = OrderGoods.objects.filter(order=order)

                total_price = 0
                # 遍历订单中的商品获取相关信息
                for sku in order_skus:
                    amount = sku.count * sku.price
                    total_price += amount
                # 获取订单的状态
                order_status = OrderInfo.ORDER_STATUS[order.order_status]
                # 计算订单的总价
                transit_price = order.transit_price
                order.total_price = total_price + transit_price
                order.status = order_status
                order.skus = order_skus

                paginator = Paginator(orders, 1)
                # 判断页码是否规范
                try:
                    page = int(page)
                except Exception as e:
                    page = 1

                if page > paginator.num_pages:
                    page = 1

                # todo:自定义列表页码
                # 总页数不足5页 显示总页数
                # 前三页 显示1~5
                # 后三页 显示后5页
                # 显示当前页的前两页 当前页 当前页的后两页

                num_page = paginator.num_pages
                if num_page < 5:
                    pages = range(1, num_page + 1)
                elif page <= 3:
                    pages = range(1, 6)
                elif page >= num_page - 2:
                    pages = range(num_page - 4, num_page)
                else:
                    pages = range(page - 2, page + 3)

                # 获取该页数据
                page_data = paginator.page(page)
            # 定义模板上下文
            context = {
                'orders': orders,
                'page_data': page_data,
                'pages': pages,
                'page': 'order'

            }

            return render(request, 'user_center_order.html', context)
        else:
            return render(request, 'user_center_order.html', {'page': 'order'})
