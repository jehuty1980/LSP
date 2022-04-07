from PIL import Image
import pillow_avif
import cv2
import numpy as np
import logging

logger = logging.getLogger('ImageLoader')
logger.setLevel(logging.DEBUG)


class ImageLoader(object):
    """
    用来读取文件，实际存储的是numpy数组，封装了cv2相应的图像操作
    """

    def __init__(self):
        self.content = None
        # self.bmp = None

    def load_img(self, fp):
        """
        读取图片并存储
        :param fp: 普通文件夹里的文件名；或由container返回的压缩文件内的fp
        :return:
        """
        img = Image.open(fp)
        if not img.mode == 'RGB':
            img = img.convert('RGB')
        # 奇怪的是，windows设备的Bitmap居然也用的BGR格式？
        self.content = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)

    def get_img(self):
        """
        返回numpy数组格式的图像数据
        :return:
        """
        return self.content

    def set_img(self, content):
        """
        :param content: numpy数组格式的图像数据
        :return:
        """
        self.content = content

    def crop(self, crop_rect: tuple):
        """
        裁剪
        :param crop_rect: (left,top,right,bottom)
        :return:
        """
        cropped_img = ImageLoader()
        cropped_img.set_img(self.content[crop_rect[1]:crop_rect[3], crop_rect[0]:crop_rect[2]])
        return cropped_img

    def resize(self, size: tuple, flip_code=0):
        """
        缩放并翻转，这是由于numpy数组转换到Bitmap时会上下翻转图像的问题
        :param flip_code: 0为默认，上下翻转，传递None不翻转
        :param size: (width,height)
        :return:
        """
        resized_img = ImageLoader()
        if self.width < size[0]:  # 放大
            # mode = cv2.INTER_LINEAR
            mode = cv2.INTER_CUBIC
        else:
            mode = cv2.INTER_AREA
        if flip_code is not None:
            resized_img.set_img(cv2.flip(cv2.resize(self.content, size, interpolation=mode), flip_code))
        else:
            resized_img.set_img(cv2.resize(self.content, size, interpolation=mode))
        return resized_img

    def rotate(self, direction=1):
        """
        旋转图像，只有90°的
        :param direction: 1:'clockwise',-1:'counterclockwise'
        :return:
        """
        rotated_img = ImageLoader()
        if direction == 1:
            rotated_img.set_img(cv2.rotate(self.content, cv2.ROTATE_90_CLOCKWISE))
        elif direction == -1:
            rotated_img.set_img(cv2.rotate(self.content, cv2.ROTATE_90_COUNTERCLOCKWISE))
        return rotated_img

    @property
    def width(self):
        if self.content is not None:
            return self.content.shape[1]
        else:
            return 0

    @property
    def height(self):
        if self.content is not None:
            return self.content.shape[0]
        else:
            return 0
