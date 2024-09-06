#! /usr/bin/python3.6

import time
import webbrowser

from PyQt5.QtCore import (QFile, QFileInfo, QPoint, QRect, QSettings, QSize,
        Qt, QTextStream, QUrl, QTimer)
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtWidgets import (QAction, QApplication, QFileDialog, QMainWindow,
        QMessageBox, QTextEdit, QGroupBox, QFormLayout, QLabel, QLineEdit, QTreeView,
        QVBoxLayout, QDialog, QMenuBar, QHBoxLayout, QPushButton, QTabWidget, QWidget)
#from PyQt5.QtWebEngineWidgets import QWebEngineView #trouble with this is - no codecs

import user_api


class MainWindow(QDialog):
    def __init__(self):
        super(QDialog, self).__init__()

        self.port = 5000 #TODO set when text box changes
        self.player_url = 'http://localhost:%s/hls/player.html' % (5000)
        #repeating status timer
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(False)
        self.update_timer.timeout.connect(self.update_server_status)
        self.update_timer.start(500)
        #form on loaded equivalent
        self.defer_init = QTimer()
        self.defer_init.setSingleShot(True)
        self.defer_init.timeout.connect(self.init_done)
        self.defer_init.start(1000)

        self.createActions()
        self.createMenus()
        #self.createToolBars()
        #self.createStatusBar()

        self.readSettings()

        #self.textPortNum.document().contentsChanged.connect(self.documentWasModified)
        
        tabWidget = QTabWidget()
        self.watch_tab = WatchTab()
        tabWidget.addTab(self.watch_tab, "Watch")
        self.broadcast_tab = BroadcastTab()
        tabWidget.addTab(self.broadcast_tab, "Broadcast")
        self.settings_tab = SettingsTab()
        tabWidget.addTab(self.settings_tab, "Settings")

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(tabWidget)
        mainLayout.setMenuBar(self.menuBar)

        self.setLayout(mainLayout)
        self.setWindowTitle("Peerstream")


#TODO maybe shouldn't be a QDialog since would have to disable ESC key?
#    def keyPressEvent(self, event):
#        print("KEY PRESSED!!")
        
    def closeEvent(self, event):
        self.stop_server()
        if self.maybeSave():
            self.writeSettings()
            event.accept()
        else:
            event.ignore()

    def about(self):
        QMessageBox.about(self, "About Application", "Simple p2p desktop sharing JKH 2018")

    def documentWasModified(self):
        self.setWindowModified(self.textEdit.document().isModified())

    def update_server_status(self):
        server_text = "Running" if user_api.is_server_running() else "Stopped"
        self.watch_tab.status_text.setText("Server status: %s" % server_text)
        self.settings_tab.status_text.setText("Server status: %s" % server_text)

        peers_text = "Connected to %d peers" % len(user_api.peer_list())
        self.watch_tab.number_peers_text.setText(peers_text)

    def init_done(self):
        #TODO pointless now but might be more to go here
        self.start_server()

    def start_server(self):
        user_api.start_server(self.port)
        time.sleep(1)
        #webbrowser.open(self.player_url)

    def stop_server(self):
        user_api.stop_server()
        
    def server_status(self):
        running = user_api.is_server_running()

    def createActions(self):
        root = QFileInfo(__file__).absolutePath()

        self.startAct = QAction(QIcon(root + '/images/new.png'), "&New", self,
                shortcut=QKeySequence.New, statusTip="Start server",
                triggered=self.startServer)

        self.aboutAct = QAction("&About", self,
                statusTip="Show the application's About box",
                triggered=self.about)

        self.aboutQtAct = QAction("About &Qt", self,
                statusTip="Show the Qt library's About box",
                triggered=QApplication.instance().aboutQt)

        self.exitAct = QAction("E&xit", self, shortcut="Ctrl+Q",
                statusTip="Exit the application", triggered=self.close)


    def createMenus(self):
        self.menuBar = QMenuBar()
        self.fileMenu = self.menuBar.addMenu("&File")
        self.fileMenu.addSeparator();
        self.fileMenu.addAction(self.exitAct)

        self.helpMenu = self.menuBar.addMenu("&Help")
        self.helpMenu.addAction(self.aboutAct)
        self.helpMenu.addAction(self.aboutQtAct)

#    def createToolBars(self):
#        self.fileToolBar = self.addToolBar("Server")
#        self.fileToolBar.addAction(self.startAct)
#
#        self.editToolBar = self.addToolBar("Edit")

#    def createStatusBar(self):
#        self.statusBar().showMessage("Ready")

    def readSettings(self):
        settings = QSettings("Trolltech", "Application Example")
        pos = settings.value("pos", QPoint(200, 200))
        size = settings.value("size", QSize(400, 400))
        self.resize(size)
        self.move(pos)

    def writeSettings(self):
        settings = QSettings("Trolltech", "Application Example")
        settings.setValue("pos", self.pos())
        settings.setValue("size", self.size())

    def maybeSave(self):
        return True

    def startServer(self):
        user_api.start_server(5000)

class WatchTab(QWidget):
    def __init__(self):
        super(WatchTab, self).__init__()
        self.createUpperGroupBox()
        self.createLowerGroupBox()
        watchLayout = QVBoxLayout()
        watchLayout.addWidget(self.upperGroupBox)
        watchLayout.addWidget(self.lowerGroupBox)
        
        self.setLayout(watchLayout)
        
    def createLowerGroupBox(self):
        self.lowerGroupBox = QGroupBox("Select channel")
        
    def createUpperGroupBox(self):
        self.upperGroupBox = QGroupBox("Status")
        layout = QFormLayout()
        self.status_text = QLabel("Server status: Stopped")
        layout.addRow(self.status_text)
        self.number_peers_text = QLabel()
        layout.addRow(self.number_peers_text)
        self.action_text = QLabel("Current action: inactive")
        layout.addRow(self.action_text)
        self.upperGroupBox.setLayout(layout)

class SettingsTab(QWidget):
    def __init__(self):
        super(SettingsTab, self).__init__()
        self.createUpperGroupBox()
        self.createLowerGroupBox()
        
        watchLayout = QVBoxLayout()
        watchLayout.addWidget(self.upperGroupBox)
        watchLayout.addWidget(self.lowerGroupBox)
        
        self.setLayout(watchLayout)
        
    def createUpperGroupBox(self):
        self.upperGroupBox = QGroupBox("Server settings")
        layout = QFormLayout()
        layout.addRow(QLabel("Port number:"), QLineEdit("5000"))
        self.status_text = QLabel("Server status: Stopped")
        layout.addRow(self.status_text)
        self.upperGroupBox.setLayout(layout)
        
    def createLowerGroupBox(self):
        self.peersView = QTreeView()
        self.peersView.setRootIsDecorated(False)
        self.peersView.setAlternatingRowColors(True)
        
        self.lowerGroupBox = QGroupBox("Peers list")
        layout = QHBoxLayout()
        layout.addWidget(self.peersView) 

        self.lowerGroupBox.setLayout(layout)

class BroadcastTab(QWidget):
    def __init__(self):
        super(BroadcastTab, self).__init__()
        self.createFormGroupBox()
        
        broadcastLayout = QVBoxLayout()
        broadcastLayout.addWidget(self.formGroupBox)
        
        self.setLayout(broadcastLayout)
        
    def createFormGroupBox(self):
        self.formGroupBox = QGroupBox()

        
if __name__ == '__main__':

    import sys

    app = QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.show()
    sys.exit(app.exec_())

