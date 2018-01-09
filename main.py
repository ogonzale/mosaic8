#! -*- coding: utf-8 -*-

import sys  # We need sys so that we can pass argv to QApplication
import os
import math
import numpy as np
from scipy import misc

import MosaicDesign  # This file holds our MainWindow and all design related things
from PyQt5 import QtCore, QtGui, QtWidgets  # Import some of the PyQt5 modules...  QtCore,
from PyQt5.QtWidgets import (QApplication, QFileDialog, QGraphicsScene, QMessageBox, QGraphicsTextItem,
                             QGraphicsItem, QLineEdit)
from PyQt5.QtCore import Qt, QDir, QRectF, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage

# v1 first deployment.
# v2 rot90.
# v3 Added positions in real space for each item and the possibility to compute the distance between pics.
# v4 Improved the save and open project features.
# v5 We have to get rid of scroll bars when exporting.

globalversion = '1.5'

MosaicDesign.globalversion = globalversion


class MovablePixmapItem(QtWidgets.QGraphicsPixmapItem):
    def __init__(self, pixmap, *args, **kwargs):
        QtWidgets.QGraphicsPixmapItem.__init__(self, pixmap, *args, **kwargs)
        self.setFlags(QtWidgets.QGraphicsItem.ItemIsMovable |
                      QtWidgets.QGraphicsItem.ItemSendsGeometryChanges |
                      QtWidgets.QGraphicsItem.ItemIsSelectable |
                      QtWidgets.QGraphicsItem.ItemIsFocusable |
                      QtWidgets.QGraphicsItem.ItemClipsChildrenToShape |
                      QtWidgets.QGraphicsItem.ItemContainsChildrenInShape |
                      QtWidgets.QGraphicsItem.ItemDoesntPropagateOpacityToChildren)

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.ItemPositionHasChanged:
            pass

        return QtWidgets.QGraphicsPixmapItem.itemChange(self, change, value)


class DiagramTextItem(QGraphicsTextItem):
    lostFocus = pyqtSignal(QGraphicsTextItem)

    selectedChange = pyqtSignal(QGraphicsItem)

    def __init__(self, parent=None, scene=None):
        super(DiagramTextItem, self).__init__(parent, scene)

        self.setFlags(QtWidgets.QGraphicsItem.ItemIsMovable |
                      QtWidgets.QGraphicsItem.ItemIsSelectable |
                      QtWidgets.QGraphicsItem.ItemIgnoresParentOpacity|
                      QtWidgets.QGraphicsItem.isVisible)

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.ItemPositionHasChanged:  # QGraphicsItem.ItemSelectedChange:
            self.selectedChange.emit(self)  # pass
        return QtWidgets.QGraphicsTextItem.itemChange(self, change, value)  # value

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.lostFocus.emit(self)
        super(DiagramTextItem, self).focusOutEvent(event)


class MosaicApp(QtWidgets.QMainWindow, MosaicDesign.Ui_MainWindow):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)  # This is defined in design file automatically

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, 850, 750)

        self.graphicsView.keyPressEvent = self.keyPressEvent

        self.comboBox.addItem(" 1 pixel step")
        self.comboBox.addItem("0.5 pixel step")

        self.comboBox.activated[str].connect(self.onActivated)

        self.comboBox_2.addItem("No Rounding")
        self.comboBox_2.addItem("0 Order")
        self.comboBox_2.addItem("1 Order")

        self.comboBox_2.activated[str].connect(self.roundingPos)

        self.horizontalSlider.valueChanged.connect(self.lcdNumber.display)
        self.horizontalSlider.valueChanged.connect(self.changeValue)

        self.actionOpen.setShortcut("Ctrl+O")
        self.actionOpen.setStatusTip("Open new File")
        self.actionOpen.triggered.connect(self.open)

        self.actionQuit.triggered.connect(self.close)
        self.actionQuit.setShortcut("Ctrl+Q")

        self.actionSave.setShortcut("Ctrl+S")
        self.actionSave.setStatusTip("Save current images positions")
        self.actionSave.triggered.connect(self.save_imagepos)

        self.actionImport.setShortcut("Ctrl+I")
        self.actionImport.setStatusTip("Import an ongoing project")
        self.actionImport.triggered.connect(self.import_project)

        self.actionExport.setShortcut("Ctrl+E")
        self.actionExport.setStatusTip("Export current canvas to an image")
        self.actionExport.triggered.connect(self.exportScene)

        self.actionClose_project.setShortcut("Ctrl+X")
        self.actionClose_project.setStatusTip("Close the current project and open a new one restarting canvas")
        self.actionClose_project.triggered.connect(self.cleanScene)

        self.actionAbout.triggered.connect(self.about)
        self.setMouseTracking(True)

        self.checkBox.setCheckState(Qt.Checked)
        self.checkBox.stateChanged.connect(self.changeTextItems)

        self.pushButton.clicked.connect(self.computeDistance)

        self.pushButton_2.clicked.connect(self.setreference)

        self.off_setX = 0  # Offset of the images in order to put one of them at (0, 0)
        self.off_setY = 0  # 3000.00
        self.unit_ratio = 1.0  # ratio length / pixels
        self.n = 0
        self.j = 0
        self.picName = []
        self.c = 0
        self.item_i = []
        self.label_i = []
        self.group = []
        self.names = []
        self.opacity = 0.85
        self.delta = ()
        self.deltax, self.deltay = 0, 0
        self.text = ""
        self.firstinput = [0, 0]
        self.secondinput = [1, 1]
        self.k = 1.0
        self.selectedItems = []
        self.currentFolder = ""
        self.graphicsView.wheelEvent = self.nwheelEvent
        self.order = 6
        self.refItem = ""

    def setreference(self):
        self.getParameters()
        counter =0
        for item in self.scene.selectedItems():
            self.deltax = round(float(self.off_setX) - float(item.x()) * self.unit_ratio, self.order)
            self.deltay = round(float(self.off_setY) - float(item.y()) * self.unit_ratio, self.order)
            # self.refItem = self.picName
            for elements in self.item_i:
                counter += 1
                if elements == item:
                    # print self.picName[counter-1]
                    self.refItem = self.picName[counter-1]

    def onActivated(self, text):
        if text == " 1 pixel step":
            self.k = 1.0
        elif text == "0.5 pixel step":
            self.k = 0.5

    def roundingPos(self, text):
        if text == "No Rounding":
            self.order = 6
        elif text == "0 Order":
            self.order = 0
        elif text == "1 Order":
            self.order = 1
        return self.order

    def updatePositions(self):
        for pics in self.item_i:
            pics.setPos(round(float(pics.x()), self.order), round(float(pics.y()), self.order))
            # print pics.x(), pics.y()

        # print self.order

    def graphWidget(self):
        self.graphicsView.scale(0.8, 0.8)
        self.setMinimumSize(1200, 900)

    def nwheelEvent(self, event):
        self.scaleView(math.pow(2.0, -event.angleDelta().y() / 240.0))

    def scaleView(self, scaleFactor):
        factor = self.graphicsView.transform().scale(scaleFactor, scaleFactor).mapRect(QRectF(0, 0, 1, 1)).width()

        if factor < 0.07 or factor > 100:
            return
        self.graphicsView.scale(scaleFactor, scaleFactor)
        self.graphicsView.setTransformationAnchor(self.graphicsView.AnchorUnderMouse)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Left:
            self.delta = (-1.0 * self.k, 0.0 * self.k)
            self.keyMovePics()
        elif event.key() == Qt.Key_Right:
            self.delta = (1.0 * self.k, 0.0 * self.k)
            self.keyMovePics()
        elif event.key() == Qt.Key_Up:
            self.delta = (0.0 * self.k, -1.0 * self.k)
            self.keyMovePics()
        elif event.key() == Qt.Key_Down:
            self.delta = (0.0 * self.k, 1.0 * self.k)
            self.keyMovePics()

    def changeValue(self, value):
        self.opacity = value/100.0
        for pics in self.item_i:
            pics.setOpacity(self.opacity)

    def keyMovePics(self):
        self.getParameters()
        for item in self.scene.selectedItems():
            item.moveBy(self.delta[0], self.delta[1])

    def save_imagepos(self):
        name = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File', QDir.homePath(), "Text Files (*.txt)")
        self.getParameters()
        if name[0][-3::] != "txt":
            name = str(name[0])+".txt"
        elif name[0][-3::] == "txt":
            name = str(name[0])

        if name is not u'':  # if os.path.isfile(str(name[0])):
            fileToSave = open(name, 'wt')
            if fileToSave:
                counter = 0
                if counter == 0 :
                    self.getParameters()
                    self.text = str("#" + '''{'ofx':%s, 'ofy':%s, 'px':%s, 'au':%s,'refobj':%s}''' % (self.off_setX,
                                    self.off_setY, self.secondinput[0], self.secondinput[1],
                                                                                        str("'" + self.refItem + "'")))
                    print self.text
                    fileToSave.write(self.text + "\n")
                for pics in self.item_i:
                    counter += 1
                    self.text = str(str(pics.pos()).replace("PyQt5.QtCore.QPointF", "") + " " + self.picName[counter-1])
                    fileToSave.write(self.text + "\n")  # round(float(pics.x()), 1)
                # print self.text
                # print pics.pos()

    def resetViewingZoom(self):
        self.graphicsView.resetTransform()
        self.graphicsView.fitInView(0, 0, 850, 750, Qt.KeepAspectRatio)
        # QtWidgets.QScrollBar()

    def exportScene(self):
        self.resetViewingZoom()
        exportName = QtWidgets.QFileDialog.getSaveFileName(self, "Export File", QDir.homePath(),
                                                           "Image Files (*.tiff)")  # *.png, *.jpg, *.bmp,
        if exportName and exportName[0] is not u'':
            pix = QtWidgets.QWidget.grab(self.graphicsView)
            pix.save(str(exportName[0] + ".tiff"), "tiff")  # I have made as default tiff to preserve the quality

    def computeDistance(self):
        self.getParameters()
        X = []
        Y = []
        c = 0
        for item in self.scene.selectedItems():
            X.append(round(float(item.x()) * self.unit_ratio, 2) + self.deltax)
            Y.append(round(float(item.y()) * self.unit_ratio, 2) + self.deltay)
            c +=1
            # print c
        if c == 2 :
            a = np.array([X[0],Y[0]])
            b = np.array([X[1],Y[1]])
            self.label_3.setText("The distance between the selected pics it is: \n" + "for A: " + str(a) +
                                 "     and  B: " + str(b) + "    B --> A : " + str(a - b) +
                                 "    A --> B : " + str(b - a) + "     arbitrary units")
        else:
            self.label_3.setText("Please be sure to select a couple of images to compute the distance")

    def changeTextItems(self, state):
        self.getParameters()
        if state == Qt.Checked:
            for i in range(0, len(self.label_i)):
                self.label_i[i].setVisible(True)
        else:
            for i in range(0, len(self.label_i)):
                self.label_i[i].setVisible(False)

    def import_project(self):
        fileToImp = QFileDialog.getOpenFileName(self, "Open Project", QDir.homePath(),
                                                "Text Files (*.txt)")  # Previously as file descriptor was also *
        self.getParameters()
        if fileToImp and fileToImp[0] is not u'':
            f = open(fileToImp[0])
            counter = 0
            for line in f:
                if counter == 0:
                    # line = line.rstrip('\n')
                    meta = eval(line[1:])
                    self.off_setX = meta["ofx"]
                    self.off_setY = meta["ofy"]
                    self.secondinput[0] = meta["px"]
                    self.secondinput[1] = meta["au"]
                    self.lineEdit_1.setText(str(self.off_setX))
                    self.lineEdit_2.setText(str(self.off_setY))
                    self.lineEdit_3.setText(str(self.secondinput[0]))
                    self.lineEdit_4.setText(str(self.secondinput[1]))
                    print meta, meta["refobj"]

                elif counter != 0:
                    xn = 0
                    yn = 0
                    xpos = ""
                    ypos = ""
                    c = 0
                    b = 0
                    # counter += 1
                    direct = ""
                    line = line.rstrip('\n')  # Here we are getting rid of the end of the line character ('\n')
                    for char in line:
                        if char == "(":
                            xn = 1
                        if char == ",":
                            xn = 0
                            yn = 1
                        if char == ")":
                            yn = 0
                            c = 1
                        if xn == 1:
                            xpos += char
                        if yn == 1:
                            ypos += char
                        if c == 1:
                            if char != " ":
                                direct += char
                    xpos = xpos[1::]
                    fxpos = round(float(xpos), 1)  # float(xpos)
                    ypos = ypos[2::]
                    fypos = round(float(ypos), 1)  # float(ypos)

                    findirect = direct[1:]
                    for let in str(findirect):
                        b += 1
                        if let == ".":
                            ext = str(findirect[b:])

                    if ext == "jpg" or ext == "png" or ext == "bmp" or ext == "tif" or ext == "tiff":
                        itemToLoad = QtGui.QPixmap(findirect, "24")
                    elif ext == "txt" or ext == "ssv" or ext == "dat":
                        predataImage = np.genfromtxt(findirect, dtype=np.float32)
                        dataImage = np.rot90(predataImage, k=1)  # TwinMic specific rotation
                        tmpfn = '/tmp/mosaicSketch.%s.png' % os.getpid()  # temporary - and not unique name
                        temp = open(tmpfn, 'w+b')
                        misc.imsave(temp.name, dataImage)
                        itemToLoad = QPixmap(temp.name)
                        temp.close()
                        os.remove(tmpfn)
                    self.item_i.append(MovablePixmapItem(itemToLoad))
                    self.item_i[-1].setOpacity(self.opacity)
                    self.scene.addItem(self.item_i[-1])
                    self.item_i[-1].setPos(fxpos, fypos)
                    self.item_i[-1].setFlag(True)
                    self.picName.append(findirect)
                    if findirect == meta["refobj"]:
                        self.item_i[-1].setSelected(True)
                    # print str(round(float(self.item_i[-1].x()), 2)) + ", " + str(round(float(self.item_i[-1].y()), 2))
                    self.label_i.append(QtWidgets.QGraphicsTextItem())
                    self.label_i[-1].setParentItem(self.item_i[-1])
                    self.label_i[-1].setPlainText(
                        str(round(float(self.deltax) + (self.item_i[-1].x() * self.unit_ratio), 2))
                        + ", " + str(round(float(self.deltay) + (self.item_i[-1].y() * self.unit_ratio), 2))
                    )

                    self.label_i[-1].adjustSize()
                    self.item_i[-1].mousePressEvent = self.handleMouse
                counter += 1
            self.graphicsView.setScene(self.scene)
            self.graphicsView.setRenderHint(QtGui.QPainter.Antialiasing)
            self.graphicsView.show()
            self.setreference()
            self.currentFolder = findirect  # self.picName[-1][:- (len(QDir(self.picName[-1]).dirName()) + 1)]
            self.label_9.setText(self.currentFolder)

    def open(self):
        fileName = QFileDialog.getOpenFileNames(self, "Import Image/Data Files", QDir.homePath(),
                                                "Image/Data Files (*.png *.jpg *.bmp *.tif *.tiff *.ssv *.dat)")
        self.getParameters()
        i = 1
        for o in range(0, len(fileName[0])):
            self.picName.append(fileName[0][o])
            c = 0
            if fileName:
                for let in self.picName[-1]:
                    c += 1
                    if let == ".":
                        ext = self.picName[-1][c:]
                # print self.picName[-1], ext
                if ext == "jpg" or ext == "png" or ext == "bmp" or ext == "tif":
                    i += 1
                    itemToLoad = QtGui.QPixmap(fileName[0][o], "24")
                elif ext == "ssv" or ext == "dat":
                    i += 1
                    predataImage = np.genfromtxt(self.picName[-1], dtype=np.float32)
                    dataImage = np.rot90(predataImage, k=1) # TwinMic specific rotation
                    tmpfn = '/tmp/mosaicSketch.%s.png' % os.getpid()  # temporary - and not unique name
                    temp = open(tmpfn, 'w+b')
                    misc.imsave(temp.name, dataImage)
                    itemToLoad = QPixmap(temp.name)
                    temp.close()
                    os.remove(tmpfn)

                self.item_i.append(MovablePixmapItem(itemToLoad))
                self.item_i[-1].setOpacity(self.opacity)  # render the images semi-transparent self.opacity
                self.scene.addItem(self.item_i[-1])
                self.item_i[-1].setPos(10 + i * 50, 10 + i * 50)
                self.item_i[-1].setFlag(True)

                self.label_i.append(QtWidgets.QGraphicsTextItem())
                self.label_i[-1].setParentItem(self.item_i[-1])
                self.label_i[-1].setPlainText(
                    str(round(float(self.deltax) + (self.item_i[-1].x() * self.unit_ratio), 2))
                    + ", " + str(round(float(self.deltay) + (self.item_i[-1].y() * self.unit_ratio), 2))
                )
                self.label_i[-1].adjustSize()
                self.item_i[-1].mousePressEvent = self.handleMouse
                self.graphicsView.setScene(self.scene)
                self.graphicsView.setRenderHint(QtGui.QPainter.Antialiasing)
                self.graphicsView.show()
                self.names = fileName[0][o]

            # print QDir(self.picName[-1]).dirName()
            self.currentFolder = self.picName[-1][:- (len(QDir(self.picName[-1]).dirName())+1)]
            self.label_9.setText(self.currentFolder)

    def cleanScene(self):
        reply = QMessageBox.question(self,"Are you sure?",
                                     'Do you want to close the project to begin a new one?', QMessageBox.Yes |
                                     QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.off_setX = 0  # Offset of the images in order to put one of them at (0, 0)
            self.off_setY = 0  # 3000.00
            self.unit_ratio = 1.0  # ratio length / pixels
            self.n = 0
            self.j = 0
            self.picName = []
            self.c = 0
            self.item_i = []
            self.label_i = []
            self.group = []
            self.names = []
            self.opacity = 0.85
            self.delta = ()
            self.deltax, self.deltay = 0, 0
            self.text = ""
            self.firstinput = [0, 0]
            self.secondinput = [1, 1]
            self.k = 1.0
            self.selectedItems = []
            self.currentFolder = ""
            self.graphicsView.wheelEvent = self.nwheelEvent
            self.order = 6
            self.scene.clear()
            self.label_9.setText("")
            self.label_3.setText("The distance between the selected pics it is: \n" + "for A:  " +
                                 "     and  B: " + "     B --> A : " + "      arbitrary units")
            self.lineEdit_1.setText("")
            self.lineEdit_2.setText("")
            self.lineEdit_3.setText("")
            self.lineEdit_4.setText("")

    def handleMouse(self, event):
        self.getParameters()
        self.updatePositions()
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        if modifiers == QtCore.Qt.ShiftModifier:
            pass
        elif modifiers == QtCore.Qt.ControlModifier:
            pass
        elif modifiers == (QtCore.Qt.ControlModifier |
                           QtCore.Qt.ShiftModifier):
            pass
        else:
            for i in range(0, len(self.label_i)):
                self.label_i[i].setPlainText(
                    str(round(float(self.deltax) + (self.item_i[i].x() * self.unit_ratio), self.order))
                    + ", " + str(round(float(self.deltay) + (self.item_i[i].y() * self.unit_ratio), self.order))
                )

    def about(self):
        QMessageBox.about(self, "About",
                          """ 
    The aim of this App it is to aid in data reconstruction             
    for the Coherent Diffraction Imaging (CDI) experiments.     

    This code it is been developed by:

       Elettra's Scientific Computing team.

                            Copyright 2017.
                            """)

    def getParameters(self):
        if QLineEdit.text(self.lineEdit_1) != "":
            self.firstinput[0] = QLineEdit.text(self.lineEdit_1)
            try:
                self.off_setX = float(self.firstinput[0])
            except ValueError:
                QMessageBox.warning(self, "Upps... wrong input!",
                                    "Its seems that you have entered a non valid input for the off set(x)",
                                    QMessageBox.Ok)
        if QLineEdit.text(self.lineEdit_2) != "":
            self.firstinput[1] = QLineEdit.text(self.lineEdit_2)
            try:
                self.off_setY = float(self.firstinput[1])
            except ValueError:
                QMessageBox.warning(self, "Upps... wrong input!",
                                    "Its seems that you have entered a non valid input for the off set(y)",
                                    QMessageBox.Ok)
        if QLineEdit.text(self.lineEdit_3) != "" and QLineEdit.text(self.lineEdit_4) != "":
            # self.secondinput[0] = QLineEdit.text(self.lineEdit_3)
            # self.secondinput[1] = QLineEdit.text(self.lineEdit_4)
            try:
                self.secondinput[0] = float(QLineEdit.text(self.lineEdit_3))  # and float(QLineEdit.text(self.lineEdit_3)) != 0
            except ValueError:
                QMessageBox.warning(self, "Upps... wrong input!",
                                    "Its seems that you have entered a non valid input for the 'Sample Width pixels'",
                                    QMessageBox.Ok)
            try:
                self.secondinput[1] = float(QLineEdit.text(self.lineEdit_4))  # and float(QLineEdit.text(self.lineEdit_4)) != 0
            except ValueError:
                QMessageBox.warning(self, "Upps... wrong input!",
                                    "Its seems that you have entered a non valid input for the 'Sample Width a.u'",
                                    QMessageBox.Ok)
            if self.secondinput[0] > 0 and self.secondinput[1] > 0 :
                self.unit_ratio = float(self.secondinput[1]) / float(self.secondinput[0])
            else:
                QMessageBox.warning(self, "Upps... wrong input!",
                                    "Please check your input for the 'Sample Width pixels/a.u'",
                                    QMessageBox.Ok)
        return self.order

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Are you Leaving?',
                                     "Are you sure to Quit?", QMessageBox.Yes |
                                     QMessageBox.No)

        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()


def main():
    app = QApplication(sys.argv)  # A new instance of QApplication
    form = MosaicApp()  # We set the form to be our MosaicApp (design)
    form.show()  # Show the form

    app.exec_()  # and execute the app


if __name__ == '__main__':  # if we're running file directly and not importing it
    main()  # run the main function
