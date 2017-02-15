import os, sys
import numpy as np
import wx
import cv2
import logging
import rospy
import roslaunch
from cv_bridge import CvBridge, CvBridgeError
from sensor_msgs.msg import Image, TimeReference
import threading
import message_filters as mfilters
LOG = logging.getLogger(__name__)
FORMAT = '%(funcName)20s(%(lineno)s)-%(levelname)s:%(message)s'
CH = logging.Handler()
CH.setFormatter(logging.Formatter(FORMAT))
LOG.addHandler(CH)
LOG.setLevel(logging.DEBUG)
SHAPE = (500, 900)


def getbitmap(main_panel, img):
    '''
    numpy array to bitmap
    '''
    psize = main_panel.GetSize()
    '''
    if img.shape[0] != psize[0] or img.shape[1] != psize[1]:
        copy = cv2.resize(img, (psize[0], psize[1]))
    else:
        copy = img.copy()
    '''
    image = wx.Image(img.shape[1], img.shape[0])
    image.SetData(img.tostring())
    wx_bitmap = image.ConvertToBitmap()
    return wx_bitmap

EVT_READY_TYPE = wx.NewEventType()
EVT_READY = wx.PyEventBinder(EVT_READY_TYPE, 1)
class ReadyEvent(wx.PyCommandEvent):
    '''
    Event to signal that data from ros is loaded
    '''
    def __init__(self, *args, **kwargs):
        wx.PyCommandEvent.__init__(self,*args,**kwargs)

class Data(object):
    def __init__(self):
        self.hand = None
        self.skel = None
        self.class_name = None
    def add(self, hand, skel, class_name):
        self.hand = hand
        self.skel = skel
        self.class_name = class_name

class ROSThread(threading.Thread):
    def __init__(self, parent, data):
        threading.Thread.__init__(self)
        self._parent = parent
        self._data = data
    def run(self):
        '''
        Overrides Thread.run . Call Thread.start(), not this.
        '''
        subscriber = ROSSubscriber(self._parent,
                                   self._data)
        rospy.init_node('canvas', anonymous=False, disable_signals=True)
        rospy.spin()


class ROSSubscriber(object):
    def __init__(self, parent, data):
        self._parent = parent
        self._data = data
        self.hand_sub = mfilters.Subscriber(
            "hand", Image)
        self.skel_sub = mfilters.Subscriber(
            "skeleton", Image)
        self.clas_sub = mfilters.Subscriber(
            "class", TimeReference)
        self.image_ts = mfilters.TimeSynchronizer(
            [self.hand_sub, self.skel_sub,
             self.clas_sub], 30)
        self.image_ts.registerCallback(
            self.callback)
        self.bridge = CvBridge()
    def callback(self, hand, skel, class_name):
        hand = self.bridge.imgmsg_to_cv2(hand,
                                              desired_encoding=
                                              'passthrough')
        skel = self.bridge.imgmsg_to_cv2(skel,
                                              desired_encoding=
                                              'passthrough')
        self._data.add(hand, skel, class_name.source)
        evt = ReadyEvent(EVT_READY_TYPE, -1)
        wx.PostEvent(self._parent, evt)

class Canvas(wx.Panel):
    def __init__(self, parent, data):
        wx.Panel.__init__(self, parent)
        [self.height, self.width] = data.shape[:2]
        self.SetMinSize(wx.Size(self.height, self.width))
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.data = data

    def on_paint(self, event):
        painter = wx.AutoBufferedPaintDC(self)
        painter.Clear()
        painter.DrawBitmap(
            getbitmap(self, self.data), 0, 0)


class MainFrame(wx.Frame):
    def __init__(self,parent, id_, title):
        wx.Frame.__init__(self,parent, id_, title)
        self.Bind(EVT_READY, self.on_process)
        self.data = Data()
        self.drawing_im = None
        self.canvas = None
        self.ros_thread = ROSThread(self,self.data)
        self.ros_thread.start()

    def on_process(self, event):
        inp = np.tile(self.data.hand[:, :, None] % 255, (1, 1, 3))
        if self.drawing_im is None:
            self.drawing_im = np.zeros_like(inp)
        self.drawing_im[self.data.skel[-1, -1,0], self.data.skel[-1,-1,1]] = [0, 255 , 0]
        inp = np.minimum(self.drawing_im+inp)
        inp[inp>255] = inp
        inp = inp.astype(np.uint8)
        if self.canvas is None:
            self.canvas = Canvas(self, inp)
        else:
            self.canvas.data = inp
        self.canvas.Refresh(False)



def main():
    '''
    main function
    '''
    logging.basicConfig(format=FORMAT)
    app = wx.App(0)
    frame = MainFrame(None, -1, 'Painter')
    frame.Show(True)
    app.MainLoop()

if __name__ == '__main__':
    main()