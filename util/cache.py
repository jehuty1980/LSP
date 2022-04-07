# from __future__ import absolute_import, with_statement
from pubsub import pub
import wx
from threading import Thread, Lock, Semaphore
import logging
import traceback
from util.imgloader import ImageLoader
from util.canvas import Canvas

log = logging.getLogger('cache')
log.setLevel(logging.ERROR)


class ImageCacheLoadRequest(object):
    def __init__(self, file_name, panels, canvases):
        self.file_name = file_name
        self.panels = panels
        self.canvases = canvases
        self.img = None

    def __call__(self):
        # 特殊函数调用方法，会在cache线程中调用，注意，如果直接命中缓存，此函数是不会被调用的
        self.img = ImageLoader()
        pub.sendMessage('busy', msg=(True,))
        self.img.load_img(self.file_name)
        # self.update_canvases(True)  # 目前来看，可以不放在单独线程

    def update_canvases(self, refresh=False):
        if not self.canvases:  # 不存在的话，需要初始化canvases实例
            self.canvases = {}
            for key in self.panels.keys():
                self.canvases[key] = Canvas(self.panels[key])
        for key in self.panels.keys():
            self.canvases[key].calculate_zoom(self.img, self.panels[key])
            # 面板隐藏时不进行图像处理，仅记录img引用
            if self.panels[key].is_shown:
                self.canvases[key].zoom(refresh)
                pub.sendMessage('main_control.refresh_panel', msg=(self.panels[key],))

    def __eq__(self, other):
        if not other:
            return False
        cont_eq = (self.file_name is other.file_name)
        return cont_eq

    def __ne__(self, other):
        return not self == other


class ImageCache(object):
    def __init__(self, settings):
        self.settings = settings
        pub.subscribe(self.on_load_image, 'cache.load_image')
        pub.subscribe(self.on_clear_pending, 'cache.clear_pending')
        pub.subscribe(self.on_flush, 'cache.flush')
        pub.subscribe(self.on_program_closed, 'program.closed')
        self.queue = []
        self.qlock = Lock()
        self.cache = []
        self.clock = Lock()
        self.semaphore = Semaphore(0)
        self.thread = Thread(target=self.run)
        self.thread.setDaemon(True)
        self.thread.start()
        self.processing_request = None

    def on_load_image(self, msg):
        request = msg[0]
        hit = False
        # 锁住缓存，如果查找到有的话，直接分发消息
        with self.clock:
            for req in self.cache:
                if req == request:
                    log.debug('main: cache hit')
                    self.notify_image_loaded(req)
                    hit = True
        # 如果没有找到，而且接收的消息也不是正在处理的请求，则生成新请求并插入队列
        if not hit and request != self.processing_request:
            log.debug('main: cache miss')
            self._put_request(request)

    def on_image_loaded(self, request):
        # 将缓存进行锁定，超出容量就将末尾去掉
        # 然后将结果存入缓存的第一项
        with self.clock:
            if len(self.cache) >= 5:  # 5张图片缓存
                self.cache.pop()
            self.cache.insert(0, request)
            # 发消息出去，带有request结果的信息
            self.notify_image_loaded(request)

    def on_flush(self, msg):
        # 清空缓存
        with self.clock:
            while self.cache:
                self.cache.pop()

    def notify_image_loaded(self, request):
        pub.sendMessage('cache.image_loaded', msg=(request,))

    def notify_image_load_error(self, request, exception, tb):
        pub.sendMessage('cache.image_load_error', msg=(request, exception, tb))

    def _put_request(self, request):
        # 锁住队列，在请求队列的头部插入新的请求，并通过释放semaphore来继续run线程
        with self.qlock:
            if request not in self.queue:
                log.debug('main: inserting request')
                self.queue.insert(0, request)
                log.debug('main: releasing...')
                self.semaphore.release()

    def on_clear_pending(self, msg):
        # 清空请求队列
        with self.qlock:
            while self.queue:
                self.queue.pop()

    def on_program_closed(self, msg):
        log.debug('main: on closed')
        # log.debug('main: clearing pending...')
        # 直接调用
        self.on_clear_pending(None)
        # 在队列中插入None请求
        with self.qlock:
            log.debug('main: adding None request')
            self.queue.insert(-1, None)
        log.debug('main: releasing...')
        # 释放semaphore让run线程执行
        self.semaphore.release()
        log.debug('main: joining...')
        # 等待run线程所有代码执行完毕
        self.thread.join()
        print('cache cleared')

    def run(self):
        log.debug('thread: running...')
        while True:
            log.debug('thread: acquiring...')
            # 因为初始计数为0，只有当run即本线程之外有release()调用时才往下执行
            self.semaphore.acquire()
            log.debug('thread: acquired. reading request...')
            while True:
                with self.qlock:
                    # 如果清空了所有请求，则跳出循环
                    if not self.queue:
                        log.debug('thread: queue empty')
                        break
                    req = self.queue.pop()
                # 如果出现了None请求，则结束整个函数，即跳出run线程
                if req is None:
                    return
                self.processing_request = req
                e, tb = None, None
                try:
                    log.debug('thread: running request...')
                    req()
                    log.debug('thread: request processed, notifying')
                    wx.CallAfter(self.on_image_loaded, req)
                    log.debug('thread: request processed notified')
                except Exception as e:
                    tb = traceback.format_exc()
                    log.debug('thread: request raised an exception')
                    # log.debug(tb)
                finally:
                    self.processing_request = None
                if tb:
                    wx.CallAfter(self.notify_image_load_error, req, e, tb)
