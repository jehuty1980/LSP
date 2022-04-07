import wx
import wx.adv
from pathlib import Path
from pubsub import pub


class MyFrame(wx.Frame):
    """
    因为不想用系统热键，绑了一堆top level的消息处理函数
    """

    def __init__(self, title):

        super(MyFrame, self).__init__(None, title=title, size=(
            wx.SystemSettings.GetMetric(wx.SYS_SCREEN_X) // 5 * 4,
            wx.SystemSettings.GetMetric(wx.SYS_SCREEN_Y) // 5 * 4))
        self.status_bar = self.CreateStatusBar()
        self.status_bar.SetFieldsCount(3, [-14, -1, -1])
        self.status_bar.SetStatusText('Press F1 for help!', 0)
        self.cwd = Path.cwd()
        self.full_screen = False

        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDown)
        # self.Bind(wx.EVT_MAXIMIZE,self.OnMaximize)
        pub.subscribe(self.on_update_status, 'container.update_status_bar')
        pub.subscribe(self.on_busy, 'busy')
        pub.subscribe(self.open_file_dialog, 'open_file')
        pub.subscribe(self.on_fullscreen, 'toggle_fullscreen')

    def OnClose(self, evt):
        pub.sendMessage('program.closed', msg=None)
        self.Destroy()

    def on_busy(self, msg):
        if msg[0]:
            self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
        else:
            # print('not busy')
            # 不延时调用的话，光标有可能设置不回来
            wx.CallLater(250, self.SetCursor, wx.Cursor(wx.CURSOR_ARROW))

    def open_file_dialog(self, msg):
        wildcard ='Supported Files|*.blp;*.bmp;*.bufr;*.cur;*.dcx;*.dds;*.dib;*.eps;*.ps;*.fit;*.fits;*.flc;*.fli;*.ftc;*.ftu;*.gbr;*.gif;*.grib;*.h5;*.hdf;*.icns;*.ico;*.im;*.iim;*.jfif;*.jpe;*.jpeg;*.jpg;*.j2c;*.j2k;*.jp2;*.jpc;*.jpf;*.jpx;*.mpeg;*.mpg;*.msp;*.pcd;*.pcx;*.pxr;*.apng;*.png;*.pbm;*.pgm;*.pnm;*.ppm;*.psd;*.bw;*.rgb;*.rgba;*.sgi;*.ras;*.icb;*.tga;*.vda;*.vst;*.tif;*.tiff;*.webp;*.emf;*.wmf;*.xbm;*.xpm;*.zip;*.rar;*.cbz;*.cbr|All Files|*.*'
        file_dialog = wx.FileDialog(parent=self, message="打开图像文件",
                                    defaultDir=str(self.cwd),
                                    style=wx.FD_OPEN,
                                    wildcard=wildcard)
        if file_dialog.ShowModal() == wx.ID_OK:
            pub.sendMessage('open.file', msg=(file_dialog.GetPath(),))
        file_dialog.Destroy()

    def OnKeyDown(self, evt):
        keycode = evt.GetKeyCode()
        # print('keycode:{},raw keycode:{} pressed'.format(keycode, evt.GetRawKeyCode()))
        if keycode == 79:  # O
            self.open_file_dialog(None)
        if keycode == 13:  # enter
            self.on_fullscreen(None)
        if keycode == 27:  # esc
            self.Close()
        if keycode == 340:  # F1
            self.about_box()
        if keycode == 70:  # F
            pub.sendMessage('frame.show_panels', msg=('file_list',))
        if keycode == 72:  # H
            pub.sendMessage('frame.show_panels', msg=(None,))
        if keycode == 84:  # T
            pub.sendMessage('frame.load_layout', msg=None)
        if keycode == 76:  # L
            pub.sendMessage('frame.rotate_image', msg=(-1,))
        if keycode == 82:  # R
            pub.sendMessage('frame.rotate_image', msg=(1,))
        if keycode == 32 or keycode == 68 or keycode == 316 or keycode == 367:
            pub.sendMessage('container.load_image', msg=(None, 1))
        if keycode == 8 or keycode == 65 or keycode == 314 or keycode == 366:
            pub.sendMessage('container.load_image', msg=(None, -1))

    def on_fullscreen(self, msg):
        self.full_screen = not self.full_screen
        self.ShowFullScreen(self.full_screen)

    def on_update_status(self, msg):
        idx, length, name, path, w, h = msg
        pos = '  {:>5d}/{:<5d}'.format(idx + 1, length)
        size = '  {} x {}'.format(w, h)
        self.status_bar.SetStatusText('  '+name, 0)
        self.status_bar.SetStatusText(size, 1)
        self.status_bar.SetStatusText(pos, 2)

        self.cwd = path

    def about_box(self):
        description = """  LSP是专门用来浏览差分图像的软件，极简设计，支持常见图像和压缩文件格式。
  全名Launch Specific Pictures：启动特殊图片，有两个浮动面板，可对主画布进行局部放大。
  又名Locally Stretched Photos：局部拉伸照片，好了，我编不下去了，你懂的，下面是快捷键:
  ++++++++++++++++++++++++++++++++++++++++++++++++++++++++
             打开帮助    F1
             打开文件    (Ctrl +) O，左键双击
             全屏切换    Enter，中键单击
             退出程序    Esc
             恢复面板    (Ctrl +) H
             图像列表    (Ctrl +) F切换隐藏和显示
             局部放大    右键框选（每个面板）
             重置比例    右键双击（每个面板）
             适应尺寸    Ctrl + 中键（每个面板，在适应全部、高度和宽度中轮换）
             浏览图片    滚轮，Backspace|Space，←|→，PgUp|PgDn，(Ctrl +) A|D
             放大图片    Ctrl + 滚轮
             拖动图片    左键拖拽
             旋转图片    (Ctrl +) R|L
  ++++++++++++++++++++++++++++++++++++++++++++++++++++++++
  键盘操作时关闭中文输入法可不按Ctrl，图片缩放限制为窗口的一半到四倍"""
        licence = """LSP is a free software
免费的，欢迎来看源码"""
        info = wx.adv.AboutDialogInfo()
        # info.SetIcon(wx.Icon('xxx.png', wx.BITMAP_TYPE_PNG))
        info.SetName('LSP')
        info.SetVersion('1.0.0')
        info.SetDescription(description)
        info.SetCopyright('(C) 2022 - 2233')
        info.SetWebSite('https://gitee.com/jehuty1980')
        info.SetLicence(licence)
        info.AddDeveloper('jehuty1980')

        wx.adv.AboutBox(info)
