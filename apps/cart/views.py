from django.shortcuts import render, redirect
from django.views.generic import View
from django.http import JsonResponse
from django.core.urlresolvers import reverse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.Maxin import LoginRequiredMixin
# Create your views here.


# /cart/add
class CartAddView(View):
    """添加购物车"""

    def post(self, request):
        """处理购物车数据"""

        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 获取数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 校验数据
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        try:
            count = int(count)
        except Exception:
            return JsonResponse({'res': 2, 'errmsg': '商品数量出错'})

        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        # 处理数据
        con = get_redis_connection('default')
        key = 'cart_{}'.format(user.id)
        # 更新购物车数据
        old_count = con.hget(key, sku.id)
        if old_count:
            count = count + int(old_count)

        # 判断库存量
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '库存量不足'})

        con.hset(key, sku.id, count)
        cart_count = con.hlen(key)

        # 返回应答
        return JsonResponse({'res': 5, 'cart_count': cart_count, 'msg': '加入购物车成功'})


# /cart
class CartShowView(LoginRequiredMixin, View):
    """显示购物车的信息"""
    def get(self, request):
        # 返回购物车信息页面
        # 获取购物车数据
        con = get_redis_connection('default')
        user = request.user
        key = 'cart_{}'.format(user.id)
        cart_dict = con.hgetall(key)
        # 获取商品sku对象和商品总数量
        skus = []
        total_count = 0

        for sku_id, count in cart_dict.items():
            sku = GoodsSKU.objects.get(id=sku_id)
            amount = sku.price * int(count)
            sku.count = count
            sku.amount = amount
            skus.append(sku)
            total_count += int(count)
        # 定义模板上下文
        content = {
            'skus': skus,
            'total_count': total_count
        }

        # 返回应答
        return render(request, 'cart.html', content)


# /cart/update
class CartUpdateView(View):
    """更新购物车数据"""
    def post(self, request):
        # 更新购物车
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 获取数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 校验数据
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        try:
            count = int(count)
        except Exception:
            return JsonResponse({'res': 2, 'errmsg': '商品数量出错'})

        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        # 处理数据
        user = request.user
        con = get_redis_connection('default')
        key = 'cart_{}'.format(user.id)

        # 判断库存量
        if count > sku.stock:
            print('存量不足', count)
            return JsonResponse({'res': 4, 'errmsg': '库存量不足'})
        # 更新购物车数据
        con.hset(key, sku.id, count)

        # 返回商品总数量
        total_count = 0
        vals = con.hvals(key)
        for i in vals:
            total_count += int(i)

        # 返回应答
        return JsonResponse({'res': 5, 'total_count': total_count, 'msg': '加入购物车成功'})


# /cart/delete
class CartDeleteView(View):
    """删除购物车商品"""
    def post(self, request):
        # 删除用户指定的商品
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 获取数据
        sku_id = request.POST.get('sku_id')

        # 校验数据
        try:
            GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 1, 'errmsg': '该商品不存在'})

        # 业务处理
        user = request.user
        con = get_redis_connection('default')
        key = 'cart_{}'.format(user.id)
        con.hdel(key, sku_id)

        # 获取购物车的商品总数量
        # total_count = pass
        return JsonResponse({'res': 2, 'msg': '成功删除'})
        # 返回应答
