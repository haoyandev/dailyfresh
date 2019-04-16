from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.views.generic import View
from django.core.cache import cache
from django.core.paginator import Paginator
from goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner, GoodsSKU
from order.models import OrderGoods
from django_redis import get_redis_connection
from utils.GetCartData import get_cart_data
# Create your views here.


class IndexView(View):
    """首页"""
    def get(self, request):
        """返回首页"""
        # 查看是否有缓存
        content = cache.get('index')
        if content is None:

            # 获取商品种类信息
            types = GoodsType.objects.all()

            # 获取首页轮播商品信息
            goods_banners = IndexGoodsBanner.objects.all().order_by('-index')
            print(goods_banners)
            # 获取首页促销活动信息
            promotion_banners = IndexPromotionBanner.objects.all().order_by('-index')

            for type in types:
                # 获取首页分类商品的图片展示
                display_image = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1)
                display_title = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0)

                # 动态的给type增加display_image display_title两个属性
                type.display_image = display_image
                type.display_title = display_title
            # 组织上下文
            content = {
                'types': types,
                'goods_banners': goods_banners,
                'promotion_banners': promotion_banners
            }

            # 设置缓存
            cache.set('index_data', content, 3600)
        # 获取购物车信息
        cart_count = 0
        cart_count = get_cart_data(request)

        content.update({'cart_count': cart_count})
        return render(request, 'index.html', content)


class DetailView(View):
    """商品详情页面"""
    def get(self, request, goods_id):
        # 返回商品详情页面
        try:
            goods = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            # 没有该商品
            return redirect(reverse('goods:index'))

        # 获取相关信息
        types = GoodsType.objects.all()
        new_goods = GoodsSKU.objects.filter(type=goods.type).order_by('-create_time')[:2]
        order_goods = OrderGoods.objects.filter(sku=goods).exclude(comment='')

        # 获取购物车数据
        cart_count = get_cart_data(request)

        # 如果用户登录了 添加到历史记录
        user = request.user
        if user.is_authenticated():
            con = get_redis_connection('default')
            key = 'history_{}'.format(user.id)
            con.lrem(key, 0, goods.id)
            con.lpush(key, goods.id)

        # 定义模板上下文
        content = {
            'types': types,
            'goods': goods,
            'new_goods': new_goods,
            'order_goods': order_goods,
            'cart_count': cart_count
        }

        return render(request, 'detail.html', content)


# /list/type_id/page?sort=
class ListView(View):
    """商品列表"""
    def get(self, request, type_id, page):
        """返回商品列表"""
        # 获取该种类信息
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            return redirect(reverse('goods:index'))

        # 获取种类信息
        types = GoodsType.objects.all()

        # 获取新品信息
        new_goods = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]

        # 获取购物车信息
        cart_count = get_cart_data(request)

        # 判断排序方式 获取相应type的所有商品
        sort = request.GET.get('sort')
        if sort == 'price':
            # 价格排序
            skus = GoodsSKU.objects.filter(type=type).order_by('-price')
        elif sort == 'sales':
            # 销量排序
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            # 默认排序 按照id
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')

        paginator = Paginator(skus, 20)
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
            pages = range(1, num_page+1)
        elif page <= 3:
            pages = range(1, 6)
        elif page >= num_page-2:
            pages = range(num_page-4, num_page)
        else:
            pages = range(page-2, page+3)



        # 获取该页数据
        page_data = paginator.page(page)
        # 定义模板上下文
        content = {
            'type': type,
            'types': types,
            'new_goods': new_goods,
            'page_data': page_data,
            'paginator': paginator,
            'page': page,
            'cart_count': cart_count,
            'sort': sort,
            'pages': pages
        }

        return render(request, 'list.html', content)

