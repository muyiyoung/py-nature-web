import logging
logging.basicConfig(level=logging.INFO)
__author__ = 'Jimu Yang'

'''
async web application
'''

# import asyncio, os, json, time
# from datetime import datetime
# from aiohttp import web

# def index(request): 
#     return web.Response(body=b'<h1>Awesome muyi</h1>')

# async def init(loop):
#     app = web.Application(loop=loop)
#     app.router.add_route('GET', '/', index)
#     srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
#     logging.info('server started at http://localhost:9000...')
#     return srv

# loop = asyncio.get_event_loop()
# loop.run_until_complete(init(loop))
# loop.run_forever()

import os, json, time
from datetime import datetime
import asyncio
from aiohttp import web
from jinja2 import Environment, FileSystemLoader

from orm.orm_core import create_pool
from webcore.coroweb import add_routes, add_static
from handlers import cookie2user, COOKIE_NAME

def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    options = dict(
        autoescape = kw.get('autoescape', True),
        block_start_string = kw.get('block_start_string', '{%'),
        block_end_string = kw.get('block_end_string', '%}'),
        variable_start_string = kw.get('variable_start_string', '{{'),
        variable_end_string = kw.get('variable_end_string', '}}'),
        auto_reload = kw.get('auto_reload', True),
    )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path to: %s', path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters is not None:
        for name, filt in filters.items():
            env.filters[name] = filt
    app['__templating__'] = env

async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request: %s %s', request.method, request.path)
        return await handler(request)
    return logger

async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s', str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request form: %s', str(request.__data__))
        return await handler(request)
    return parse_data

# 鉴权Factory
async def auth_factory(app, handler):
    async def auth(request):
        logging.info('checking user: %s %s' % (request.method, request.path))
        request.__user__ = None
        cookie_str = request.cookies.get(COOKIE_NAME)
        if cookie_str:
            user = await cookie2user(cookie_str)
            if user:
               logging.info('set current user: %s' % user.email) 
               request.__user__ = user
        # 管理员需要登录
        if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
            return web.HTTPFound('/signin')
        return await handler(request)
    return auth

async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler...')
        result = await handler(request)
        if isinstance(result, web.StreamResponse):
            return result
        if isinstance(result, bytes):
            resp = web.Response(body=result)    
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(result, str):
            if result.startswith('redirect:'):
                return web.HTTPFound(result[9:])
            resp = web.Response(body=result.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(result, dict):
            template = result.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(result, ensure_ascii=False, default=lambda o:o.__dict__).encode('utf-8'))
            else:
                resp = web.Response(body=app['__templating__'].get_template(template).render(**result).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(result, int) and result >= 100 and result < 600:
            return web.Response(body=result)
        if isinstance(result, tuple) and len(result) == 2:
            t, m = result
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(status=t, body=str(m))
        # default:
        resp = web.Response(body=str(result).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response

def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

async def init(loop):
    await create_pool(loop=loop, host='127.0.0.1', port=3306, user='www-data', password='www-data', database='py_nature_web')
    app = web.Application(loop=loop, middlewares=[
        logger_factory, auth_factory, response_factory
    ])
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, 'handlers')
    add_static(app)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()

