from django.contrib import admin
from django.core.cache import cache
from goods.models import GoodsType, GoodsSKU, Goods, IndexTypeGoodsBanner, IndexPromotionBanner, IndexGoodsBanner
# Register your models here.


class GoodsAdmin(admin.ModelAdmin):
    def __str__(self):
        return self.name



admin.site.register(GoodsType)
admin.site.register(GoodsSKU)
admin.site.register(Goods, GoodsAdmin)
admin.site.register(IndexTypeGoodsBanner)
admin.site.register(IndexPromotionBanner)
admin.site.register(IndexGoodsBanner)