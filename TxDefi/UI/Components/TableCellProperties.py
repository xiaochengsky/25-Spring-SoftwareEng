from abc import abstractmethod
class ClickCallBack:
    @abstractmethod
    def click():
        pass

class TextProperty:
    def __init__(self, text: str, styleTag = "default"):
        self.text = text
        self.styleTag = styleTag

class ClickableProperty(TextProperty):
    def __init__(self, clickCallback, text: str, styleTag = "default"):
        TextProperty.__init__(self, text, styleTag)
        self.clickCallback = clickCallback

class ImageProperty(ClickableProperty):
    def __init__(self, imagePath: str, clickCallback, text: str, styleTag = "default"):
        ClickableProperty.__init__(self, clickCallback, text, styleTag)
        self.image_path = imagePath
        self.show_image = True


