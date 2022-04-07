import wx
from pubsub import pub


# todo:也许会有一天加入thumbnail功能？遥遥无期...

class FileList(wx.ListCtrl):
    def __init__(self, parent):
        super(FileList, self).__init__(parent, style=wx.LC_REPORT | wx.LC_VIRTUAL)
        self.InsertColumn(0, 'Picture List')
        self.container = None
        self._auto_selection = False
        self.SetItemCount(0)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected)
        pub.subscribe(self.on_img_loaded, 'container.load_image')
        pub.subscribe(self.on_selection_changed, 'container.update_status_bar')

    def OnGetItemText(self, item, column):
        """
        风格使用wx.LC_VIRTUAL时，必须重载的消息处理函数
        自动读入数据
        :param item: 行号？
        :param column: 列号
        :return:
        """
        if column == 0:
            if self.container is not None:
                return self.container.get_name(item)
            else:
                return ''

    def OnSize(self, evt):
        """
        根据窗口尺寸设置列宽
        :param evt:
        :return:
        """
        self.SetColumnWidth(0, self.GetSize().x)

    def on_img_loaded(self, msg):
        if self.container is not None:
            self.SetItemCount(0)
            self.SetItemCount(len(self.container.img_list))

    def OnItemSelected(self, evt):
        if not self._auto_selection:  # 不设置此开关会来回发消息
            # print(evt.GetIndex(), 'selected')
            pub.sendMessage('container.load_image', msg=(evt.GetIndex(), 0))

    def on_selection_changed(self, msg):
        idx = msg[0]
        self._auto_selection = True
        try:
            self.SetItemState(idx, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
                              wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED)
            self.EnsureVisible(idx)
        finally:
            self._auto_selection = False


class FileListPanel(wx.Panel):
    def __init__(self, parent):
        super(FileListPanel, self).__init__(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.file_list = FileList(self)
        sizer.Add(self.file_list, 1, wx.EXPAND, 0)
        self.SetSizer(sizer)

    def set_container(self, container):
        self.file_list.container = container
