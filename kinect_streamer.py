import os, sys
import logging
import signal
import numpy as np
import cv2
import rospy
import roslaunch
import message_filters as mfilters
from cv_bridge import CvBridge, CvBridgeError
from sensor_msgs.msg import Image, TimeReference
from math import pi
import time
import class_objects as co
import extract_and_process_rosbag as epr
import svm_training as st
KINECT = None
def signal_handler(sig, frame):
    '''
    Signal handler for CTRL-C interrupt (SIGINT)
    '''
    LOG.info('Mean processing time: '+
                 str(np.sum(np.diff(KINECT.time))/(len(KINECT.time) - 1))+' s')
    KINECT.process.stop()
    sys.exit(0)
class Kinect(object):
    '''Kinect Processing Class'''

    def __init__(self):
        #Kinect requirements
        ####
        node = roslaunch.core.Node("kinect2_bridge", "kinect2_bridge")
        rospy.set_param('fps_limit',10)
        launch = roslaunch.scriptapi.ROSLaunch()
        launch.start()
        self.process = launch.launch(node)
        if self.process.is_alive():
            print 'Starting subscribers to Kinect..'
        signal.signal(signal.SIGINT, signal_handler)
        self.image_sub = rospy.Subscriber(
            "/kinect2/sd/image_depth",Image,self.callback, queue_size=10)
        self.image_pub = rospy.Publisher("hand", Image)
        self.class_pub = rospy.Publisher("class", TimeReference)
        self.skel_pub = rospy.Publisher("skeleton", Image)
        rospy.init_node('kinect_stream', anonymous=False)
        self.bridge = CvBridge()
        ###
        # Hand action recognition
        self.open_kernel = np.ones((5, 5), np.uint8)
        self.prepare_frame = epr.DataProcess(save=False)
        self.svm = st.SVM()
        self.svm.run_training(retrain_svms=False,
                              retrain_dicts=False,
                              buffer_size = 25)#load dictionaries and svms
        self.time = []
    def callback(self, data):
        '''
        Callback function, <data> is the depth image
        '''
        try:
            frame = self.bridge.imgmsg_to_cv2(data, desired_encoding="passthrough")
        except CvBridgeError as err:
            print err
            return
        data = self.prepare_frame.process(frame, low_ram=False, derotate=False)
        try:
            processed = data['hand'].frames[0]
            [angle,center]=data['hand'].info[0]
        except (KeyError, IndexError):
            LOG.info('No hand found')
            return
        self.prepare_frame.data = {}
        derotated = co.pol_oper.derotate(
                        processed,
                        angle,
                        center)
        cv2.imshow('test', (derotated%255).astype(np.uint8))
        cv2.waitKey(10)
        recognized_class = self.svm.run_testing(derotated)
        self.time.append(time.time())
        if recognized_class is not None:
            self.image_pub.publish(self.bridge.cv2_to_imgmsg(
                processed, "passthrough"))
            msg = TimeReference()
            msg.source = recognized_class
            self.class_pub.publish(msg)
            self.skel_pub.publish(self.bridge.cv2_to_imgmsg(
                np.array(self.prepare_frame.skeleton.skeleton,np.int32)))
KINECT = Kinect()

LOG = logging.getLogger('__name__')
CH = logging.StreamHandler()
CH.setFormatter(logging.Formatter(
    '%(funcName)20s()(%(lineno)s)-%(levelname)s:%(message)s'))
LOG.handlers = []
LOG.addHandler(CH)
LOG.setLevel('INFO')
def main():
    rospy.spin()
if __name__=='__main__':
    main()
