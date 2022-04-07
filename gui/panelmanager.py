import wx
import wx.aui
from pubsub import pub
from gui.canvaspanel import PanelInfo, CanvasPanel
from gui.filelist import FileListPanel


class MyPanelManager(wx.aui.AuiManager):
    def __init__(self, frame):
        super(MyPanelManager, self).__init__(frame)
        self.default = None
        self.panel_info_list = [PanelInfo('main_canvas'),
                                PanelInfo('canvas1', mode='FIT_HEIGHT'),
                                PanelInfo('canvas2', mode='FIT_WIDTH')]
        self.main_canvas = CanvasPanel(frame, self.panel_info_list[0])
        self.canvas_LT = CanvasPanel(frame, self.panel_info_list[1])
        self.canvas_LB = CanvasPanel(frame, self.panel_info_list[2])
        self.file_list_panel = FileListPanel(frame)
        self.layout = 0
        w, h = frame.GetSize()
        self.AddPane(self.canvas_LT, wx.aui.AuiPaneInfo().Name('canvas1').Right().Position(0).BestSize(w // 5, h // 2))
        self.AddPane(self.canvas_LB, wx.aui.AuiPaneInfo().Name('canvas2').Right().Position(1).BestSize(w // 5, h // 2))
        self.AddPane(self.main_canvas, wx.aui.AuiPaneInfo().Name('main_canvas').CenterPane())
        self.AddPane(self.file_list_panel, wx.aui.AuiPaneInfo().Name('file_list').Left().BestSize(w // 6, h))
        self.Bind(wx.EVT_SHOW, self.OnShow)
        self.Bind(wx.aui.EVT_AUI_PANE_CLOSE, self.OnPaneClose)

        pub.subscribe(self.on_show_panels, 'frame.show_panels')
        pub.subscribe(self.on_load_layout, 'frame.load_layout')

    def OnShow(self, evt):
        # 储存默认面板排列，暂时无用
        self.default = self.SavePerspective()

    def OnPaneClose(self, evt):
        # print(evt.GetPane().name)
        pub.sendMessage('auiMgr.show_pane', msg=(evt.GetPane().name, False))

    def on_show_panels(self, msg):
        name = msg[0]
        if name is not None:
            self.GetPane(name).Show(not self.GetPane(name).IsShown())
        else:
            for pane_info in self.GetAllPanes():
                pane_info.Show()
                pub.sendMessage('auiMgr.show_pane', msg=(pane_info.name, True))
        self.Update()

    def on_load_layout(self, msg):
        # 更换各种布局
        self.GetPane('file_list').Show(False)
        self.GetPane('canvas1').Show(False)
        self.GetPane('canvas2').Show(False)
        self.Update()
        w, h = self.GetManagedWindow().GetSize()
        self.layout = (self.layout + 1) % 4
        if self.layout == 0:
            self.LoadPerspective(self.default)
        if self.layout == 1:
            self.Update()
            self.GetPane('canvas1').Left().Position(0).BestSize(w // 2, h // 2).Dock().Show(True)
            self.GetPane('canvas2').Left().Position(1).BestSize(w // 2, h // 2).Dock().Show(True)
        if self.layout == 2:
            self.Update()
            self.GetPane('canvas1').Right().Position(0).BestSize(w // 2, h // 2).Dock().Show(True)
            self.GetPane('canvas2').Right().Position(1).BestSize(w // 2, h // 2).Dock().Show(True)
        if self.layout == 3:
            self.Update()
            self.GetPane('canvas1').Bottom().Position(0).BestSize(w // 2, h // 2).Dock().Show(True)
            self.GetPane('canvas2').Bottom().Position(1).BestSize(w // 2, h // 2).Dock().Show(True)
        pub.sendMessage('auiMgr.show_pane', msg=('canvas1', True))
        pub.sendMessage('auiMgr.show_pane', msg=('canvas2', True))
        self.Update()
