import ctypes
import logging
from ctypes import c_ubyte, c_void_p, byref, sizeof
from ctypes.wintypes import WORD, DWORD, LONG

import win32api
import win32con
import win32gui
import wx

from gui.canvaspanel import PanelInfo
from util.imgloader import ImageLoader

level = logging.DEBUG


class RGBQUAD(ctypes.Structure):
    _fields_ = [
        ('rgbRed', c_ubyte),
        ('rgbGreen', c_ubyte),
        ('rgbBlue', c_ubyte),
        ('rgbReserved', c_ubyte)
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', DWORD),
        ('biWidth', LONG),
        ('biHeight', LONG),
        ('biPlanes', WORD),  # 1
        ('biBitCount', WORD),  # 24
        ('biCompression', DWORD),  # BI_RGB = 0 for uncompressed format
        ('biSizeImage', DWORD),  # 0
        ('biXPelsPerMeter', LONG),  # 0
        ('biYPelsPerMeter', LONG),  # 0
        ('biClrUsed', DWORD),  # 0
        ('biClrImportant', DWORD)  # 0
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ('bmiHeader', BITMAPINFOHEADER),
        ('bmiColors', RGBQUAD * 256)
    ]


class Canvas(object):
    """
    接受CanvasPanel的消息对已经读入后的图像进行zoom，crop，paint操作的类
    需要区分主面板和其它面板，可以从传入的消息来进行区分
    """

    def __init__(self, panel_info: PanelInfo):
        self.info = panel_info
        self.img = None
        self.cropped_img = None
        self.zoomed_img = None
        self.bmi = None
        self.bmp_bits = None
        self.scale_ratio_old = 1.
        self.scale_ratio = 1.
        self.scale_offset_old = 1.
        self.scale_offset = 1.
        self.crop_old = (0., 0., 1., 1.)
        self.crop = (0., 0., 1., 1.)
        self._left = 0
        self._top = 0
        self.img_offset = wx.Size(0, 0)
        # 日志信息
        self.logger = logging.getLogger('Canvas:' + self.info.name)
        self.logger.setLevel(level)

    def calculate_zoom(self, img: ImageLoader, info: PanelInfo, crop=None):
        """
        按调用计算self.scale_ratio和self.crop，如果需要更新则返回True
        :param img:
        :param info:
        :param crop: 裁剪比例，仅在main_canvas调用其它面板时使用
        :return:
        """
        self.img = img
        # 此段进行裁剪操作计算
        if not crop:  # 传过来的是坐标而不是裁剪比例的话，代表是panel直接过来的消息，需要根据之前的crop进行计算
            self.info = info
            if info.crop_rect:
                self.logger.debug(self.info.name + '._calculate_zoom called, crop_rect given')
                crop_rect = (info.crop_rect[0] - self._left - self.img_offset.x,
                             info.crop_rect[1] - self._top - self.img_offset.y,
                             info.crop_rect[2] - self._left - self.img_offset.x,
                             info.crop_rect[3] - self._top - self.img_offset.y)
                # 计算目前展示的图片的crop ratio
                width, height = self.zoomed_img.width, self.zoomed_img.height
                crop_new = [crop_rect[0] / width, crop_rect[1] / height, crop_rect[2] / width, crop_rect[3] / height]
                for i in range(len(crop_new)):
                    crop_new[i] = crop_new[i] if crop_new[i] > 0 else 0.
                    crop_new[i] = crop_new[i] if crop_new[i] < 1 else 1.
                # 如果矩形面积不为0
                if (crop_new[2] - crop_new[0]) * (crop_new[3] - crop_new[1]) != 0:
                    w, h = self.crop[2] - self.crop[0], self.crop[3] - self.crop[1]
                    crop_final = (crop_new[0] * w + self.crop[0],
                                  crop_new[1] * h + self.crop[1],
                                  crop_new[2] * w + self.crop[0],
                                  crop_new[3] * h + self.crop[1])
                    self.logger.debug(self.info.name + ' crop_final is:' + str(crop_final))
                    # 不能裁剪得太小，其实0.01对于小图片来说也可能是有问题的，暂时不管了
                    if (crop_final[2] - crop_final[0]) > 0.01 and (crop_final[3] - crop_final[1]) > 0.01:
                        # 如果主画布处理了裁剪消息，必须重新调用其它canvas的zoom
                        if self.info.name == 'main_canvas':
                            self.logger.debug('main_canvas processed crop message!')
                            return False, crop_final
                        else:
                            self.crop_old = self.crop
                            self.crop = crop_final
                # 计算完之后一定要扔掉
                self.info.crop_rect = None
                # 同时将offset置零，使图片居中
                self.img_offset = wx.Size(0, 0)
            else:  # crop和crop_rect都是None的话，什么都不做
                pass
        else:  # 传过来的是裁剪比例的话，表明是直接调用，除了crop和offset以外的值都不要更新
            self.crop_old = self.crop
            self.crop = crop
            self.img_offset = wx.Size(0, 0)

        # 此段计算原始缩放比例，先用最佳适应尺寸，后面会设置mode来进行不同的缩放方式
        # todo:使用align来进行计算偏移，即图片左上角的位置
        try:
            if self.info.mode == 'FIT_ALL':
                if self.crop == (0., 0., 1., 1.):
                    # 不需要进行裁剪
                    if (self.img.width / self.img.height) >= (self.info.width / self.info.height):
                        scale_ratio = self.info.width / self.img.width
                    else:
                        scale_ratio = self.info.height / self.img.height
                else:
                    tmp_width = self.img.width * (self.crop[2] - self.crop[0])
                    tmp_height = self.img.height * (self.crop[3] - self.crop[1])
                    if (tmp_width / tmp_height) >= (self.info.width / self.info.height):
                        scale_ratio = self.info.width / tmp_width
                    else:
                        scale_ratio = self.info.height / tmp_height
            elif self.info.mode == 'FIT_HEIGHT':
                if self.crop == (0., 0., 1., 1.):
                    scale_ratio = self.info.height / self.img.height
                else:
                    tmp_height = self.img.height * (self.crop[3] - self.crop[1])
                    scale_ratio = self.info.height / tmp_height
            elif self.info.mode == 'FIT_WIDTH':
                if self.crop == (0., 0., 1., 1.):
                    scale_ratio = self.info.width / self.img.width
                else:
                    tmp_width = self.img.width * (self.crop[2] - self.crop[0])
                    scale_ratio = self.info.width / tmp_width
            else:
                scale_ratio = self.scale_ratio
        except ValueError:
            self.logger.debug('error:scale_ratio')
            scale_ratio = 1.
        # 需要保证缩放比例不能太小和太大，为负数会异常
        if scale_ratio < 0.01:
            scale_ratio = 0.01
        elif scale_ratio > 16:
            scale_ratio = 16.
        # 原始比例发生变化，或者裁剪发生变化，或者有滚轮缩放的消息
        if (self.scale_ratio != scale_ratio) or (self.crop_old != self.crop) or (
                self.scale_offset != info.scale_offset):
            self.scale_ratio_old = self.scale_ratio
            self.scale_ratio = scale_ratio
            if self.info.name == 'main_canvas':
                self.scale_offset_old = self.scale_offset
                self.scale_offset = info.scale_offset
            return True, None
        else:
            return False, None

    def zoom(self, refresh=False):
        """
        根据self.crop,self.scale_ratio更新self.zoomed_img
        :param refresh: 是否强制更新
        :return: bool,如果更新返回True
        """
        self.logger.debug(self.info.name + '._zoom() called,' + ' refresh flag is', refresh)
        # print(self.info.name, ': scale', self.scale_ratio, 'scale_old', self.scale_ratio_old)
        if refresh \
                or self.scale_ratio != self.scale_ratio_old \
                or self.crop != self.crop_old \
                or self.scale_offset != self.scale_offset_old:
            self.cropped_img = self.img.crop((int(self.crop[0] * self.img.width),
                                              int(self.crop[1] * self.img.height),
                                              int(self.crop[2] * self.img.width),
                                              int(self.crop[3] * self.img.height)))
            # print(self.info.name, 'scale:{:.2f},offset:{:.2f},crop_img size:({},{})'.format(self.scale_ratio,
            #                                                                                 self.scale_offset,
            #                                                                                 self.cropped_img.width,
            #                                                                                 self.cropped_img.height))
            # print('-' * 8, 'self.img.size:({},{})'.format(self.img.width, self.img.height))
            # print('-' * 8,
            #       'self.crop:({:.2f},{:.2f},{:.2f},{:.2f})'.format(self.crop[0], self.crop[1], self.crop[2],
            #                                                        self.crop[3]))
            # cv2操作的np数组在resize的时候必须4的整数倍，不然出来十分奇怪
            w = int(self.scale_ratio * self.scale_offset * self.cropped_img.width) // 4 * 4
            h = int(self.scale_ratio * self.scale_offset * self.cropped_img.height) // 4 * 4
            # 确保不会缩的太小或小于0
            w = w if w > 10 else 10
            h = h if h > 10 else 10
            self.zoomed_img = self.cropped_img.resize((w, h))
            # 生成Bitmap的信息结构
            self.bmi = BITMAPINFO(
                BITMAPINFOHEADER(sizeof(BITMAPINFOHEADER),
                                 self.zoomed_img.width,
                                 self.zoomed_img.height,
                                 1,
                                 24,  # 不带alpha通道的24位位图
                                 0, 0, 0, 0, 0, 0),
                (RGBQUAD * 256)(*[RGBQUAD(i, i, i, 0) for i in range(256)]))
            # np数组转换为Bitmap的bits
            # todo:封装
            data = self.zoomed_img.content  # .astype(np.uint8) 出bug了再说
            self.bmp_bits = data.ctypes.data_as(c_void_p)
            # 判断是否有缩放原点
            if self.info.wp is None:
                self._left = (self.info.width - self.zoomed_img.width) // 2
                self._top = (self.info.height - self.zoomed_img.height) // 2  # 中心对齐，如果顶端对齐设为0
            else:
                # print('click:', self.info.wp, 'left top:(', self._left, self._top, ') scale:', (
                #         self.scale_ratio * self.scale_offset) / (
                #               self.scale_ratio_old * self.scale_offset_old))
                self._left = self.info.wp.x - (self.info.wp.x - self.img_offset.x - self._left) * (
                        self.scale_ratio * self.scale_offset) / (
                                     self.scale_ratio_old * self.scale_offset_old) - self.img_offset.x
                self._top = self.info.wp.y - (self.info.wp.y - self.img_offset.y - self._top) * (
                        self.scale_ratio * self.scale_offset) / (
                                    self.scale_ratio_old * self.scale_offset_old) - self.img_offset.y
                self.info.wp = None
            self.crop_old = self.crop
            self.scale_ratio_old = self.scale_ratio
            self.scale_offset_old = self.scale_offset
            return True
        else:
            return False

    def move_image(self, msg):
        if msg is not None:
            info = msg[0]
            self.img_offset = info.img_offset
        # 限制整个图像的位移，公式：实际的横坐标(_left+offset.x)应落在
        # info.width-max(info.width,zoomed_img.width)与info.width-min(info.width,zoomed_img.width)之间
        real_x, real_y = self._left + self.img_offset.x, self._top + self.img_offset.y
        left_limit = self.info.width - max(self.info.width, self.zoomed_img.width)
        right_limit = self.info.width - min(self.info.width, self.zoomed_img.width)
        top_limit = self.info.height - max(self.info.height, self.zoomed_img.height)
        bottom_limit = self.info.height - min(self.info.height, self.zoomed_img.height)
        if real_x < left_limit:
            self.img_offset.x = left_limit - self._left
        if real_x > right_limit:
            self.img_offset.x = right_limit - self._left
        if real_y < top_limit:
            self.img_offset.y = top_limit - self._top
        if real_y > bottom_limit:
            self.img_offset.y = bottom_limit - self._top

    def reset(self, img=None):
        """
        重新设定crop值为默认后，强制更新画布
        :param img: 传入的话，更新画布中的源图像引用
        :return:
        """
        if img is not None:
            self.img = img
        self.scale_ratio_old = 1.
        self.scale_ratio = 1.
        self.scale_offset_old = 1.
        self.scale_offset = 1.
        self.crop_old = (0., 0., 1., 1.)
        self.crop = (0., 0., 1., 1.)
        self._left = 0
        self._top = 0
        self.img_offset = wx.Size(0, 0)
        self.info.reset()
        self.calculate_zoom(self.img, self.info)
        self.zoom(True)

    def paint_canvas(self, msg):
        """
        通过window handle对画布进行更新
        :param msg: (panel_info,hwnd)
        :return:
        """
        # info, dc = msg
        info, handle = msg
        if self.info.name == info.name:  # 不处理没有挂钩的消息
            # if self.zoomed_img:
            #     # dc.SetBackgroundMode(wx.BRUSHSTYLE_TRANSPARENT)
            #     dc.DrawBitmap(self.zoomed_img, self._left + self.img_offset.x, self._top + self.img_offset.y)
            #     if self.info.select_box is not None:
            #         dc.SetPen(wx.Pen('green', 1))
            #         dc.SetBrush(wx.Brush(wx.Colour(0, 0, 0), wx.TRANSPARENT))
            #         dc.DrawRectangle(self.info.select_box)
            #     # print('self._left, self._top', self._left, self._top)
            # else:
            #     dc.SetBackground(wx.Brush('Gray'))
            if self.zoomed_img:
                # import time
                # start_t = time.time()
                # 该段直接在copy位图前才生成dc，避免窗口闪动
                # todo:实际测试发现压缩文件压缩率高或存在特大尺寸图像时也会闪，
                #  可能是因为读取和操作图像的某些耗费资源的部分仍然还留着主线程的缘故？
                dc, ps = win32gui.BeginPaint(handle)
                win32gui.SetStretchBltMode(dc, win32con.COLORONCOLOR)
                ctypes.windll.gdi32.StretchDIBits(dc,
                                                  int(self._left + self.img_offset.x),
                                                  int(self._top + self.img_offset.y),
                                                  self.zoomed_img.width, self.zoomed_img.height,
                                                  0, 0,
                                                  self.zoomed_img.width, self.zoomed_img.height,
                                                  self.bmp_bits,
                                                  byref(self.bmi),
                                                  win32con.DIB_RGB_COLORS,
                                                  win32con.SRCCOPY)
                if self.info.select_box is not None:
                    left, top, width, height = self.info.select_box
                    if width > 1 and height > 1:
                        # 右下角减1的原因：传过来的更新区域是以select_box为基础的rect，不画在更新区域内的话无法抹掉
                        right, bottom = left + width - 1, top + height - 1
                        pen = win32gui.CreatePen(win32con.PS_DOT, 1, win32api.RGB(0, 255, 0))
                        win32gui.SelectObject(dc, pen)
                        win32gui.MoveToEx(dc, left, top)
                        win32gui.BeginPath(dc)
                        win32gui.LineTo(dc, right, top)
                        win32gui.LineTo(dc, right, bottom)
                        win32gui.LineTo(dc, left, bottom)
                        win32gui.LineTo(dc, left, top)
                        win32gui.EndPath(dc)
                        win32gui.StrokePath(dc)
                win32gui.EndPaint(handle, ps)
                # end_t = time.time()
                # print('elapsed:', end_t - start_t)

    @property
    def left(self):
        return self._left

    @property
    def top(self):
        return self._top
