from pubsub import pub
from util.cache import ImageCacheLoadRequest
from util.container import Container


class MainController(object):
    """
    主控制器
    处理并转发来自面板和其它实例的消息
    存储各画布面板的基本信息
    存储各画布面板对应的画布
    """

    def __init__(self, container: Container, panel_info_list):
        self.container = container
        self.file_name = None
        self.panels = {}  # PanelInfo dict
        for item in panel_info_list:
            self.panels[item.name] = item
        self.canvases = None
        self.img = None
        self._pending_request = None
        # 面板消息
        pub.subscribe(self.on_zoom_change, 'zoom_change')
        pub.subscribe(self.on_zoom_reset, 'zoom_reset')
        pub.subscribe(self.on_load_image, 'container.load_image')
        pub.subscribe(self.on_paint_canvas, 'panel.paint_canvas')
        pub.subscribe(self.on_image_move, 'panel.move_image')
        pub.subscribe(self.on_rotate, 'frame.rotate_image')
        pub.subscribe(self.on_show_panels, 'auiMgr.show_pane')
        # cache消息
        pub.subscribe(self.on_image_loaded, 'cache.image_loaded')

    def on_paint_canvas(self, msg):
        info, dc = msg
        if self.canvases is not None:
            self.canvases[info.name].paint_canvas(msg)

    def on_image_move(self, msg):
        if self.canvases is not None:
            info = msg[0]
            self.canvases[info.name].move_image(msg)
            pub.sendMessage('main_control.refresh_panel', msg=(info,))

    def on_zoom_change(self, msg):
        """
        处理来自各画布面板的zoom_change消息
        可能由于size，crop，zooming，load image引起
        发送refresh_panel消息
        :param msg:
        :return:
        """
        # calculate_zoom(self, img: ImageLoader, info: PanelInfo, crop_rect, crop=None):
        if self.canvases is None:
            return
        info = msg[0]
        # 如果返回crop的话表明是主画布处理了crop消息，需要二次调用其它画布进行更新
        flag, crop = self.canvases[info.name].calculate_zoom(self.img, info)
        # print(flag,crop)
        if flag:
            refreshed = self.canvases[info.name].zoom()
            if refreshed:
                pub.sendMessage('main_control.refresh_panel', msg=(info,))  # 发消息给panel更新
        elif crop:
            for key in self.canvases.keys():
                if key != 'main_canvas':
                    self.canvases[key].calculate_zoom(self.img, self.panels[key], crop=crop)
                    refreshed = self.canvases[key].zoom()
                    if refreshed:
                        pub.sendMessage('main_control.refresh_panel', msg=(self.panels[key],))  # 发消息给panel更新
                else:  # 要将主画布的选框也消除
                    pub.sendMessage('main_control.refresh_panel', msg=(info,))
        elif info.crop_rect is not None:  # 要将其它画布的选框消除
            pub.sendMessage('main_control.refresh_panel', msg=(info,))

    def on_rotate(self, msg):
        if self.canvases is None:
            return
        direction = msg[0]
        # 旋转源图像
        self.img = self.img.rotate(direction)
        for key in self.canvases.keys():
            self.canvases[key].reset(self.img)
            pub.sendMessage('main_control.refresh_panel', msg=(self.panels[key],))

    def on_zoom_reset(self, msg):
        """
        处理来自各画布面板的zoom_reset消息
        如果来源于主面板，则调用所有的画布进行重置，否则只调用对应画布重置
        :param msg:(PanelInfo,)
        :return:
        """
        if self.canvases is None:
            return
        info = msg[0]
        # if info.name == 'main_canvas':  # 遍历
        #     for key in self.canvases.keys():
        #         self.canvases[key].reset()
        #         pub.sendMessage('main_control.refresh_panel', msg=(self.panels[key],))
        # else:
        self.canvases[info.name].reset()
        pub.sendMessage('main_control.refresh_panel', msg=(info,))

    def on_show_panels(self, msg):
        name, show = msg
        if name in self.panels.keys():
            self.panels[name].is_shown = show
            if show and self.canvases is not None:
                self.canvases[name].zoom(True)

    def on_load_image(self, msg):
        """
        处理来自主画布面板的load_image消息，取得所有画布面板的信息后打包成request
        然后发送load_cache消息
        :param msg:(idx, direction)，图片索引和方向
        :return:
        """
        idx, direction = msg
        if idx is None:
            file_name = self.container.get_item(direction=direction)
        else:
            file_name = self.container.get_item(idx=idx)
        if file_name and file_name != self.file_name:
            req = ImageCacheLoadRequest(file_name, self.panels, self.canvases)
            self._pending_request = req
            pub.sendMessage('cache.load_image', msg=(req,))
            # 预读其它图像
            if direction:
                for i in range(1):
                    req = ImageCacheLoadRequest(self.container.get_item(direction * i + 1, delay=True),
                                                self.panels,
                                                self.canvases)
                    pub.sendMessage('cache.load_image', msg=(req,))

    def on_image_loaded(self, msg):
        """
        处理来自cache的image_loaded消息
        向对应面板发送refresh_panel消息，并发送update_status消息更新状态栏
        :param msg:(request,)
        :return:
        """
        req = msg[0]
        # print('o'*50)
        # print('out:', req.file_name, 'returned')
        if req == self._pending_request:
            # 从req里拿到file_name,panels,canvases,img等信息
            # print('in:', req.file_name, 'returned')
            # print('-' * 50)
            req.update_canvases(True)  # 目前看来，因为cv2的效率，放在主线程应该不会造成多大延迟
            pub.sendMessage('busy', msg=(False,))
            self.file_name = req.file_name
            self.panels = req.panels
            self.canvases = req.canvases
            self.img = req.img
            self._pending_request = None
            # 发送消息，所有面板都需要响应
            # for info in self.panels.values():
            #     pub.sendMessage('main_control.refresh_panel', msg=(info,))
            pub.sendMessage('main_control.update_status', msg=(self.img.width, self.img.height))
