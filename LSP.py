import wx
from gui.topwindow import MyFrame
from gui.panelmanager import MyPanelManager
from util.container import Container
from util.controller import MainController
from util.cache import ImageCache

# todo:增加menu bar
# todo:file list ctrl面板


if __name__ == '__main__':
    app = wx.App()
    window = MyFrame(title="LSP")
    auiMgr = MyPanelManager(window)

    file_container = Container()
    auiMgr.file_list_panel.set_container(file_container)

    img_cache = ImageCache(None)

    main_controller = MainController(file_container, auiMgr.panel_info_list)

    auiMgr.Update()
    window.Show(True)
    app.MainLoop()
