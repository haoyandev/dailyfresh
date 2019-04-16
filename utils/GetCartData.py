from django_redis import get_redis_connection


def get_cart_data(request):
    if request.user.is_authenticated():
        conn = get_redis_connection('default')
        key = 'cart_{}'.format(request.user.id)
        cart_count = conn.hlen(key)
        return cart_count