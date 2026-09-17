# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'Setup.ui'
##
## Created by: Qt User Interface Compiler version 6.10.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSizePolicy, QWidget)

class Ui_setup_form(object):
    def setupUi(self, setup_form):
        if not setup_form.objectName():
            setup_form.setObjectName(u"setup_form")
        setup_form.resize(801, 482)
        icon = QIcon()
        icon.addFile(u"icon/setup_icon.ico", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        setup_form.setWindowIcon(icon)
        self.openProj_Button = QPushButton(setup_form)
        self.openProj_Button.setObjectName(u"openProj_Button")
        self.openProj_Button.setGeometry(QRect(610, 30, 171, 51))
        font = QFont()
        font.setPointSize(12)
        self.openProj_Button.setFont(font)
        self.createProj_Button = QPushButton(setup_form)
        self.createProj_Button.setObjectName(u"createProj_Button")
        self.createProj_Button.setGeometry(QRect(610, 100, 171, 51))
        self.createProj_Button.setFont(font)
        self.proj_listWidget = QListWidget(setup_form)
        self.proj_listWidget.setObjectName(u"proj_listWidget")
        self.proj_listWidget.setGeometry(QRect(20, 30, 571, 431))
        self.proj_listWidget.setFont(font)
        self.icon_label = QLabel(setup_form)
        self.icon_label.setObjectName(u"icon_label")
        self.icon_label.setGeometry(QRect(620, 300, 161, 201))
        self.icon_label.setPixmap(QPixmap(u"icon/folder.ico"))
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.export_Button = QPushButton(setup_form)
        self.export_Button.setObjectName(u"export_Button")
        self.export_Button.setGeometry(QRect(610, 170, 171, 51))
        self.export_Button.setFont(font)

        self.retranslateUi(setup_form)

        QMetaObject.connectSlotsByName(setup_form)
    # setupUi

    def retranslateUi(self, setup_form):
        setup_form.setWindowTitle(QCoreApplication.translate("setup_form", u"\u5f00\u59cb", None))
        self.openProj_Button.setText(QCoreApplication.translate("setup_form", u"\u6253\u5f00...", None))
        self.createProj_Button.setText(QCoreApplication.translate("setup_form", u"\u65b0\u5efa", None))
        self.icon_label.setText("")
        self.export_Button.setText(QCoreApplication.translate("setup_form", u"\u5bfc\u51fa", None))
    # retranslateUi

