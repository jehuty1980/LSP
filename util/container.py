from pathlib import Path
from pubsub import pub
from zipfile import ZipFile
from rarfile import RarFile
import io
import logging

log = logging.getLogger('container')
log.setLevel(logging.ERROR)


class CompressedFiLe(object):
    """
    封装.zip和.rar压缩文件读取的类
    """

    def __init__(self, file_name: Path):
        self.file_name = file_name
        self.file = None
        if file_name.suffix.lower() in ['.rar', '.cbr']:
            self.file = RarFile(file_name)
            self.mapping = None
        elif file_name.suffix.lower() in ['.zip', 'cbz']:
            self.file = ZipFile(file_name)
            self.mapping = {}

    def list_files(self, file_format: list):
        """
        遍历整个压缩文件，暂时只读取所支持的图像文件，不支持树形目录
        :param file_format: 需要读取的后缀名类别
        :return:
        """
        if self.file is None:
            log.info('Container: invalid compressed file.')
            return False
        img_list = []
        for p in self.file.namelist():
            if Path(p).suffix.lower() in file_format:
                if self.mapping is None:  # RarFile
                    img_list.append(p)
                else:  # ZipFile
                    img_list.append(self._convert_filename(p))
        img_list.sort()
        return img_list
        # todo:可能以后会加入文件格式和修改日期的信息
        #         return [(Path(self._convert_filename(f.filename)),
        #                  datetime(*f.date_time))
        #                 for f in self.file.infolist()
        #                 if f.filename[-1] not in '\\/']

    def open_file(self, path):
        if self.mapping is None:  # RarFile
            return self.file.open(path)
        else:  # ZipFile, need name mapping
            try:
                encode_path = self.mapping[path]
            except KeyError:
                encode_path = path
            return self.file.open(encode_path)

    def _convert_filename(self, path):
        # zipfile decodes utf - 8, but not cp437
        # todo:测试对shift-jis的支持
        try:
            decoded_path = path.encode('cp437').decode('gbk')
            self.mapping[decoded_path] = path
            return decoded_path
        except UnicodeDecodeError:
            # decoded_path = path.decode('ascii', 'ignore')
            decoded_path = path
            self.mapping[decoded_path] = path
            return decoded_path


class Container(object):
    """
    图像文件读取类，可以读取整个目录或压缩文件
    """

    def __init__(self):
        self.img_supported = ['.blp', '.bmp', '.bufr', '.cur', '.dcx', '.dds', '.dib', '.eps', '.ps', '.fit', '.fits',
                              '.flc', '.fli', '.ftc', '.ftu', '.gbr', '.gif', '.grib', '.h5', '.hdf', '.icns', '.ico',
                              '.im', '.iim', '.jfif', '.jpe', '.jpeg', '.jpg', '.j2c', '.j2k', '.jp2', '.jpc', '.jpf',
                              '.jpx', '.mpeg', '.mpg', '.msp', '.pcd', '.pcx', '.pxr', '.apng', '.png', '.pbm', '.pgm',
                              '.pnm', '.ppm', '.psd', '.bw', '.rgb', '.rgba', '.sgi', '.ras', '.icb', '.tga', '.vda',
                              '.vst', '.tif', '.tiff', '.webp', '.emf', '.wmf', '.xbm', '.xpm']
        self.compressed_file_supported = ['.rar', '.zip', '.cbz', '.cbr']
        self.img_path = Path.cwd()
        self.img_idx = 0
        self.img_list = []
        self.is_compressed_file = False
        self.compressed_file = None
        self.zip_file_name_mapping = {}
        self.file_name = None
        pub.subscribe(self.on_open_file, 'open.file')
        pub.subscribe(self.on_update_status, 'main_control.update_status')

    def on_open_file(self, msg):
        file_path = Path(msg[0])
        if file_path.suffix.lower() in self.compressed_file_supported:
            if self.load_compressed_file(file_path):
                self.img_path = file_path if file_path.is_dir() else file_path.parent
                pub.sendMessage('container.load_image', msg=(self.img_idx, 0))
        else:  # 非压缩文件即打开文件夹
            if self.load_dir(file_path):
                self.img_path = file_path if file_path.is_dir() else file_path.parent
                pub.sendMessage('container.load_image', msg=(self.img_idx, 0))

    def load_dir(self, dir_name: Path):
        """
        哪怕只打开一张图片、即使选择的不是图像和压缩文件，也读取整个目录
        :param dir_name:
        :return:
        """
        if dir_name.is_dir():
            img_path = dir_name
        else:
            img_path = dir_name.parent
        img_list = []
        for p in img_path.iterdir():
            if p.suffix.lower() in self.img_supported:
                img_list.append(p)
        if len(img_list) > 0:
            img_list.sort()
            if dir_name in img_list:
                img_idx = img_list.index(dir_name)
            else:
                img_idx = 0
            self.img_path = img_path
            self.img_list = img_list
            self.img_idx = img_idx
            self.is_compressed_file = False
            self.compressed_file = None
            return True
        else:
            return False

    def load_compressed_file(self, file_name: Path):
        try:
            compressed_file = CompressedFiLe(file_name)
        except:
            log.error('Container: compressed file load fail.')
            return False
        img_list = compressed_file.list_files(self.img_supported)
        if len(img_list) > 0:
            self.img_idx = 0
            self.is_compressed_file = True
            self.file_name = file_name
            self.img_list = img_list
            self.compressed_file = compressed_file
            return True
        else:
            log.info('Container: compressed file contains no image.')
            return False

    def get_item(self, idx=None, direction=1, delay=False):
        """
        返回图像路径名，可以为ImageLoader类使用
        :param idx: 直接用idx读取
        :param direction: 无idx时，默认下一张
        :param delay: 默认同时更新现在的索引，如果delay，则代表预读到缓存
        :return:
        """
        if len(self.img_list) < 1:
            return None
        if idx is None:
            img_idx = (self.img_idx + direction) % len(self.img_list)
        else:
            img_idx = idx
        if not delay:
            self.img_idx = img_idx
        if not self.compressed_file:
            return self.img_list[img_idx]
        else:  # rar和zip的支持
            pub.sendMessage('busy', msg=(True,))
            fp = self.compressed_file.open_file(self.img_list[img_idx])
            return io.BufferedReader(fp)

    def get_name(self, idx):
        """
        返回图像的文件名字符串，不包括路径
        :param idx:
        :return:
        """
        if len(self.img_list) > 0:
            return Path(self.img_list[idx]).name

    def on_update_status(self, msg):
        """
        发送消息更新状态栏和文件列表面板
        :param msg:
        :return:
        """
        if len(self.img_list) > 0:
            w, h = msg
            name = Path(self.img_list[self.img_idx]).name
            if self.is_compressed_file:
                name = self.file_name.name + ' : ' + name
            pub.sendMessage('container.update_status_bar',
                            msg=(self.img_idx, len(self.img_list), name, self.img_path, w, h))
