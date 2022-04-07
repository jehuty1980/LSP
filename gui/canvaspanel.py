import wx
from pubsub import pub


class PanelInfo(object):
    def __init__(self, panel_name, mode='FIT_ALL', size=(400, 300)):
        self.name = panel_name
        self.width = size[0]
        self.height = size[1]
        self.rect = wx.Rect(0, 0, size[0], size[1])
        self.crop = (0., 0., 1., 1.)
        self.crop_rect = None  # 非wx.Rect类，仅记录左上右下坐标
        self.mode = mode
        self.align = 'CENTER'
        self.select_box = None
        self.img_offset = wx.Size(0, 0)  # int
        self.scale_offset = 1.
        self.wp = None  # 记录用滚轮放大时的鼠标坐标
        # self.rotation = 0  # 最后决定不进行记录了，只对单张图片进行旋转，如果整个压缩包里面全是需要旋转的，倒不如重新导一下
        # 对于旋转屏的显示器，直接改显示属性就行了
        self.is_shown = True

    def reset(self):
        self.crop = (0., 0., 1., 1.)
        self.crop_rect = None  # 非wx.Rect类，仅记录左上右下坐标
        # self.mode = 'FIT_ALL'
        # self.align = 'CENTER'
        self.select_box = None
        self.img_offset = wx.Size(0, 0)  # int
        self.scale_offset = 1.
        self.wp = None  # 记录用滚轮放大时的鼠标坐标
        self.rotation = 0  # deg


class CanvasPanel(wx.Window):
    def __init__(self, parent, info: PanelInfo):
        # 只有info.name = 'main_canvas'才能处理某些消息，同时每个panel挂钩单独的canvas，因此每个实例的info.name必须不一样
        super(CanvasPanel, self).__init__(parent)  # size=(info.width, info.height))
        self.info = info
        self.cp1 = (0, 0)  # 左键点击起始点
        self.cp2 = (0, 0)
        self.sp1 = (0, 0)  # 右键点击起始点
        self.sp2 = (0, 0)
        self.offset = None  # 图片偏移坐标
        self.left_drag_flag = False
        self.right_drag_flag = False
        self.has_image = False
        self.tmp_rect = wx.Rect(0, 0, 0, 0)  # 暂存上次视图更新时的右键框选范围

        # 消息处理
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSized)
        # 左键
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        # 右键
        self.Bind(wx.EVT_RIGHT_UP, self.OnRightUp)
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        self.Bind(wx.EVT_RIGHT_DCLICK, self.OnRightDClick)
        # 中键
        self.Bind(wx.EVT_MIDDLE_UP, self.OnMiddleUp)
        # self.Bind(wx.EVT_MIDDLE_DCLICK, self.OnMiddleDClick)
        # 鼠标移动
        self.Bind(wx.EVT_MOTION, self.OnMouseMove)
        # 滚轮
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)

        pub.subscribe(self.on_refresh, 'main_control.refresh_panel')

    def OnMouseMove(self, evt):
        if not self.has_image:
            return
        if evt.Dragging() and evt.LeftIsDown():  # 鼠标左键拖动
            self.cp2 = evt.GetPosition()
            self.SetCursor(wx.Cursor(wx.CURSOR_SIZING))
            if self.left_drag_flag:
                # move img
                if self.cp1 is not None and self.cp2 is not None:
                    x_shift, y_shift = self.cp2[0] - self.cp1[0], self.cp2[1] - self.cp1[1]
                    self.cp1 = self.cp2
                    self.info.img_offset.x += x_shift
                    self.info.img_offset.y += y_shift
                    pub.sendMessage('panel.move_image', msg=(self.info,))

        if evt.Dragging() and evt.RightIsDown():  # 鼠标右键拖动
            if self.right_drag_flag:
                self.sp2 = evt.GetPosition()
                self.SetCursor(wx.Cursor(wx.CURSOR_MAGNIFIER))
                # draw rect
                if self.sp1 is not None and self.sp2 is not None:
                    # 确保左上右下，后续好处理
                    if self.info.select_box is not None:
                        self.tmp_rect = self.info.select_box
                    self.info.select_box = wx.Rect(min(self.sp1[0], self.sp2[0]),
                                                   min(self.sp1[1], self.sp2[1]),
                                                   abs(self.sp2[0] - self.sp1[0]),
                                                   abs(self.sp2[1] - self.sp1[1]))
                    # 求最近两次select_box的并集，减少屏幕dc更新范围
                    self.Refresh(True, rect=self.tmp_rect.Union(self.info.select_box))

    def OnLeftDown(self, evt):
        if not self.has_image:
            return
        self.left_drag_flag = True
        self.cp1 = evt.GetPosition()
        self.CaptureMouse()

    def OnLeftUp(self, evt):
        if not self.has_image:
            return
        if self.left_drag_flag:
            self.left_drag_flag = False
            self.ReleaseMouse()
            self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))

    def OnLeftDClick(self, evt):
        # if self.info.name == 'main_canvas':
        pub.sendMessage('open_file', msg=None)

    def OnRightDown(self, evt):
        if not self.has_image:
            return
        self.right_drag_flag = True
        self.sp1 = evt.GetPosition()
        self.CaptureMouse()

    def OnRightUp(self, evt):
        if not self.has_image:
            return
            # 将crop放在独立的窗口，主窗口是所有缩放，而其它窗口只接收自己的消息
        if self.right_drag_flag:
            self.right_drag_flag = False
            self.sp2 = evt.GetPosition()
            # 确保左上右下
            self.info.crop_rect = (min(self.sp1[0], self.sp2[0]),
                                   min(self.sp1[1], self.sp2[1]),
                                   max(self.sp1[0], self.sp2[0]),
                                   max(self.sp1[1], self.sp2[1]))
            # print(self.info.name, 'crop_rect:', crop_rect)
            if (self.info.crop_rect[2] - self.info.crop_rect[0]) * (
                    self.info.crop_rect[3] - self.info.crop_rect[1]) == 0:
                self.info.crop_rect = None
            self.ReleaseMouse()
            self.info.select_box = None
            self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
            pub.sendMessage('zoom_change', msg=(self.info,))

    def OnRightDClick(self, evt):
        if not self.has_image:
            return
        self.info.reset()
        pub.sendMessage('zoom_reset', msg=(self.info,))

    def OnMiddleUp(self, evt):
        if evt.ControlDown() and self.has_image:
            mode_list = ['FIT_ALL', 'FIT_HEIGHT', 'FIT_WIDTH']
            self.info.mode = mode_list[(mode_list.index(self.info.mode) + 1) % len(mode_list)]
            self.OnRightDClick(None)
        else:
            pub.sendMessage('toggle_fullscreen', msg=None)

    def on_refresh(self, msg):
        if self.info.name == 'main_canvas':
            self.info.crop_rect = None
        if msg is None:  # None的话是广播，所有的面板都需要更新
            self.has_image = True
            self.Refresh()
        elif msg[0].name == self.info.name:
            self.has_image = True
            self.Refresh()

    def OnPaint(self, evt):
        if not self.has_image:
            evt.Skip()
            return
        # dc = wx.BufferedPaintDC(self)
        # dc.Clear()
        # pub.sendMessage('panel.paint_canvas', msg=(self.info, dc))
        handle = self.GetHandle()
        pub.sendMessage('panel.paint_canvas', msg=(self.info, handle))

    def OnSized(self, evt):
        # 处理面板尺寸变化消息
        evt.Skip()
        w, h = evt.GetSize()
        self.info.width, self.info.height = w, h
        self.info.rect.SetWidth(w)
        self.info.rect.SetHeight(h)
        pub.sendMessage('zoom_change', msg=(self.info,))

    def OnMouseWheel(self, evt):
        if not self.has_image:
            return
        if evt.ControlDown():  # 只有main_canvas才能响应缩放消息
            if self.info.name == 'main_canvas':
                if evt.GetWheelRotation() < 0:
                    self.info.scale_offset /= 1.1
                elif evt.GetWheelRotation() > 0:
                    self.info.scale_offset *= 1.1
                self.info.wp = evt.GetPosition()
                if 4 < self.info.scale_offset:
                    self.info.scale_offset = 4
                if self.info.scale_offset < 0.5:
                    self.info.scale_offset = 0.5
                pub.sendMessage('zoom_change', msg=(self.info,))
        else:
            if evt.GetWheelRotation() < 0:
                pub.sendMessage('container.load_image', msg=(None, 1))
            elif evt.GetWheelRotation() > 0:
                pub.sendMessage('container.load_image', msg=(None, -1))

