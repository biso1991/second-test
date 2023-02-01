import redis
from django.conf import settings

# Singleton class to maintain single instance of redis connection
class Singleton(object):
    _instance = None

    def __new__(class_, *args, **kwargs):
        if not isinstance(class_._instance, class_):
            class_._instance = object.__new__(class_, *args, **kwargs)
        return class_._instance


# Redis connection class to initialize a redis connection
class RedisConnection(Singleton):
    redis_instance = redis.StrictRedis(
        host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=1
    )
