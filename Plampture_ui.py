# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'Plampture.ui'
##
## Created by: Qt User Interface Compiler version 6.10.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMenu,
    QMenuBar, QPushButton, QSizePolicy, QSlider,
    QStatusBar, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1756, 1010)
        self.action_resolution = QAction(MainWindow)
        self.action_resolution.setObjectName(u"action_resolution")
        font = QFont()
        font.setPointSize(12)
        self.action_resolution.setFont(font)
        self.action_rate = QAction(MainWindow)
        self.action_rate.setObjectName(u"action_rate")
        self.action_rate.setFont(font)
        self.action_max_snapshots = QAction(MainWindow)
        self.action_max_snapshots.setObjectName(u"action_max_snapshots")
        self.action_max_snapshots.setFont(font)
        self.action_camera = QAction(MainWindow)
        self.action_camera.setObjectName(u"action_camera")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayoutWidget = QWidget(self.centralwidget)
        self.horizontalLayoutWidget.setObjectName(u"horizontalLayoutWidget")
        self.horizontalLayoutWidget.setGeometry(QRect(0, 0, 1751, 951))
        self.horizontalLayout = QHBoxLayout(self.horizontalLayoutWidget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.capture_widget = QWidget(self.horizontalLayoutWidget)
        self.capture_widget.setObjectName(u"capture_widget")
        self.verticalLayoutWidget = QWidget(self.capture_widget)
        self.verticalLayoutWidget.setObjectName(u"verticalLayoutWidget")
        self.verticalLayoutWidget.setGeometry(QRect(10, 10, 861, 931))
        self.verticalLayout_3 = QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.video_widget = QWidget(self.verticalLayoutWidget)
        self.video_widget.setObjectName(u"video_widget")
        self.horizontalLayoutWidget_2 = QWidget(self.video_widget)
        self.horizontalLayoutWidget_2.setObjectName(u"horizontalLayoutWidget_2")
        self.horizontalLayoutWidget_2.setGeometry(QRect(0, 0, 861, 461))
        self.horizontalLayout_3 = QHBoxLayout(self.horizontalLayoutWidget_2)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.IR_cam = QLabel(self.horizontalLayoutWidget_2)
        self.IR_cam.setObjectName(u"IR_cam")

        self.horizontalLayout_3.addWidget(self.IR_cam)

        self.RGB_cam = QLabel(self.horizontalLayoutWidget_2)
        self.RGB_cam.setObjectName(u"RGB_cam")

        self.horizontalLayout_3.addWidget(self.RGB_cam)


        self.verticalLayout_3.addWidget(self.video_widget)

        self.thumbnail_preview_widget = QWidget(self.verticalLayoutWidget)
        self.thumbnail_preview_widget.setObjectName(u"thumbnail_preview_widget")
        self.thumbnail_listWidget = QListWidget(self.thumbnail_preview_widget)
        self.thumbnail_listWidget.setObjectName(u"thumbnail_listWidget")
        self.thumbnail_listWidget.setGeometry(QRect(10, 10, 831, 441))

        self.verticalLayout_3.addWidget(self.thumbnail_preview_widget)


        self.horizontalLayout.addWidget(self.capture_widget)

        self.info_widget = QWidget(self.horizontalLayoutWidget)
        self.info_widget.setObjectName(u"info_widget")
        self.ctrl_groupBox = QGroupBox(self.info_widget)
        self.ctrl_groupBox.setObjectName(u"ctrl_groupBox")
        self.ctrl_groupBox.setGeometry(QRect(10, 690, 841, 251))
        font1 = QFont()
        font1.setPointSize(14)
        self.ctrl_groupBox.setFont(font1)
        self.ctrl_groupBox.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.ctrl_groupBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.QR_Button = QPushButton(self.ctrl_groupBox)
        self.QR_Button.setObjectName(u"QR_Button")
        self.QR_Button.setGeometry(QRect(30, 30, 79, 81))
        self.SNAP_Button = QPushButton(self.ctrl_groupBox)
        self.SNAP_Button.setObjectName(u"SNAP_Button")
        self.SNAP_Button.setGeometry(QRect(140, 30, 79, 81))
        self.NEXT_Button = QPushButton(self.ctrl_groupBox)
        self.NEXT_Button.setObjectName(u"NEXT_Button")
        self.NEXT_Button.setGeometry(QRect(30, 140, 171, 81))
        self.info_groupBox = QGroupBox(self.info_widget)
        self.info_groupBox.setObjectName(u"info_groupBox")
        self.info_groupBox.setGeometry(QRect(10, 10, 841, 571))
        self.info_groupBox.setFont(font1)
        self.info_groupBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.verticalLayoutWidget_2 = QWidget(self.info_groupBox)
        self.verticalLayoutWidget_2.setObjectName(u"verticalLayoutWidget_2")
        self.verticalLayoutWidget_2.setGeometry(QRect(10, 20, 821, 631))
        self.infoConsel_verticalLayout = QVBoxLayout(self.verticalLayoutWidget_2)
        self.infoConsel_verticalLayout.setObjectName(u"infoConsel_verticalLayout")
        self.infoConsel_verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.user_ico_label = QLabel(self.verticalLayoutWidget_2)
        self.user_ico_label.setObjectName(u"user_ico_label")
        self.user_ico_label.setScaledContents(False)
        self.user_ico_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.infoConsel_verticalLayout.addWidget(self.user_ico_label)

        self.name_label = QLabel(self.verticalLayoutWidget_2)
        self.name_label.setObjectName(u"name_label")
        self.name_label.setFont(font1)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.infoConsel_verticalLayout.addWidget(self.name_label)

        self.id_label = QLabel(self.verticalLayoutWidget_2)
        self.id_label.setObjectName(u"id_label")
        self.id_label.setFont(font1)
        self.id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.infoConsel_verticalLayout.addWidget(self.id_label)

        self.capture_timestamp_label = QLabel(self.verticalLayoutWidget_2)
        self.capture_timestamp_label.setObjectName(u"capture_timestamp_label")
        self.capture_timestamp_label.setFont(font1)
        self.capture_timestamp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.infoConsel_verticalLayout.addWidget(self.capture_timestamp_label)

        self.fill_label = QLabel(self.verticalLayoutWidget_2)
        self.fill_label.setObjectName(u"fill_label")

        self.infoConsel_verticalLayout.addWidget(self.fill_label)

        self.ap_widget = QWidget(self.info_widget)
        self.ap_widget.setObjectName(u"ap_widget")
        self.ap_widget.setGeometry(QRect(10, 590, 841, 111))
        self.IR_ap_groupBox = QGroupBox(self.ap_widget)
        self.IR_ap_groupBox.setObjectName(u"IR_ap_groupBox")
        self.IR_ap_groupBox.setGeometry(QRect(10, 10, 231, 80))
        self.IR_ap_groupBox.setFont(font1)
        self.IR_bright_ctrl_horizontalSlider = QSlider(self.IR_ap_groupBox)
        self.IR_bright_ctrl_horizontalSlider.setObjectName(u"IR_bright_ctrl_horizontalSlider")
        self.IR_bright_ctrl_horizontalSlider.setGeometry(QRect(10, 10, 160, 22))
        self.IR_bright_ctrl_horizontalSlider.setOrientation(Qt.Orientation.Horizontal)
        self.IR_contrast_ctrl_horizontalSlider = QSlider(self.IR_ap_groupBox)
        self.IR_contrast_ctrl_horizontalSlider.setObjectName(u"IR_contrast_ctrl_horizontalSlider")
        self.IR_contrast_ctrl_horizontalSlider.setGeometry(QRect(10, 30, 160, 22))
        self.IR_contrast_ctrl_horizontalSlider.setOrientation(Qt.Orientation.Horizontal)
        self.IR_exposure_ctrl_horizontalSlider = QSlider(self.IR_ap_groupBox)
        self.IR_exposure_ctrl_horizontalSlider.setObjectName(u"IR_exposure_ctrl_horizontalSlider")
        self.IR_exposure_ctrl_horizontalSlider.setGeometry(QRect(10, 50, 160, 22))
        self.IR_exposure_ctrl_horizontalSlider.setOrientation(Qt.Orientation.Horizontal)
        self.RGB_ap_groupBox = QGroupBox(self.ap_widget)
        self.RGB_ap_groupBox.setObjectName(u"RGB_ap_groupBox")
        self.RGB_ap_groupBox.setGeometry(QRect(290, 10, 181, 80))
        self.RGB_ap_groupBox.setFont(font1)
        self.RGB_bright_ctrl_horizontalSlider = QSlider(self.RGB_ap_groupBox)
        self.RGB_bright_ctrl_horizontalSlider.setObjectName(u"RGB_bright_ctrl_horizontalSlider")
        self.RGB_bright_ctrl_horizontalSlider.setGeometry(QRect(10, 20, 160, 22))
        self.RGB_bright_ctrl_horizontalSlider.setOrientation(Qt.Orientation.Horizontal)
        self.RGB_contrast_ctrl_horizontalSlider = QSlider(self.RGB_ap_groupBox)
        self.RGB_contrast_ctrl_horizontalSlider.setObjectName(u"RGB_contrast_ctrl_horizontalSlider")
        self.RGB_contrast_ctrl_horizontalSlider.setGeometry(QRect(10, 40, 160, 22))
        self.RGB_contrast_ctrl_horizontalSlider.setOrientation(Qt.Orientation.Horizontal)
        self.RGB_exposure_ctrl_horizontalSlider = QSlider(self.RGB_ap_groupBox)
        self.RGB_exposure_ctrl_horizontalSlider.setObjectName(u"RGB_exposure_ctrl_horizontalSlider")
        self.RGB_exposure_ctrl_horizontalSlider.setGeometry(QRect(10, 60, 160, 22))
        self.RGB_exposure_ctrl_horizontalSlider.setOrientation(Qt.Orientation.Horizontal)
        self.info_groupBox.raise_()
        self.ctrl_groupBox.raise_()
        self.ap_widget.raise_()

        self.horizontalLayout.addWidget(self.info_widget)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1756, 33))
        self.menusetting = QMenu(self.menubar)
        self.menusetting.setObjectName(u"menusetting")
        self.menusetting.setFont(font)
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menusetting.menuAction())
        self.menusetting.addAction(self.action_camera)
        self.menusetting.addSeparator()
        self.menusetting.addAction(self.action_resolution)
        self.menusetting.addSeparator()
        self.menusetting.addAction(self.action_max_snapshots)
        self.menusetting.addSeparator()
        self.menusetting.addAction(self.action_rate)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.action_resolution.setText(QCoreApplication.translate("MainWindow", u"resolution\n"
"", None))
        self.action_rate.setText(QCoreApplication.translate("MainWindow", u"rate", None))
        self.action_max_snapshots.setText(QCoreApplication.translate("MainWindow", u"max snapshots", None))
        self.action_camera.setText(QCoreApplication.translate("MainWindow", u"camera", None))
        self.IR_cam.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.RGB_cam.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.ctrl_groupBox.setTitle(QCoreApplication.translate("MainWindow", u"\u63a7\u5236\u9762\u677f", None))
        self.QR_Button.setText(QCoreApplication.translate("MainWindow", u"\u626bQR\u7801", None))
        self.SNAP_Button.setText(QCoreApplication.translate("MainWindow", u"\u62cd\u6444", None))
        self.NEXT_Button.setText(QCoreApplication.translate("MainWindow", u"\u4e0b\u4e00\u4e2a...", None))
        self.info_groupBox.setTitle(QCoreApplication.translate("MainWindow", u"\u4fe1\u606f\u9762\u677f", None))
        self.user_ico_label.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.name_label.setText(QCoreApplication.translate("MainWindow", u"\u59d3\u540d\uff1a", None))
        self.id_label.setText(QCoreApplication.translate("MainWindow", u"\u8eab\u4efdID: ", None))
        self.capture_timestamp_label.setText(QCoreApplication.translate("MainWindow", u"\u62cd\u6444\u65f6\u95f4: ", None))
        self.fill_label.setText("")
        self.IR_ap_groupBox.setTitle(QCoreApplication.translate("MainWindow", u"IR\u6444\u50cf\u5934\u8c03\u8282", None))
        self.RGB_ap_groupBox.setTitle(QCoreApplication.translate("MainWindow", u"RGB\u6444\u50cf\u5934\u8c03\u8282", None))
        self.menusetting.setTitle(QCoreApplication.translate("MainWindow", u"setting", None))
    # retranslateUi

