import pyqtgraph as pg
from pyqtgraph.Qt import QtGui
#from PyQt4 import QtGui

#from PyQt4.Qwt5.anynumpy import *
#
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

class Plot2dWidget(pg.GraphicsLayoutWidget):
    def __init__(self, *args):
        pg.GraphicsLayoutWidget.__init__(self, *args)
        self.view = self.addViewBox()
#        self.view.setAspectLocked(True)
        self.img = pg.ImageItem(border='w')
        self.view.addItem(self.img)
        
    def setImage(self, img):
        self.img.setImage(img)
        

class Plot0dWidget(QtGui.QWidget):        
    def __init__(self, *args):
        QtGui.QWidget.__init__(self, *args)
        self.plot = pg.PlotWidget()
        self.curveColors = [
                                   QtGui.QColor("#FF0000"), #Red
                                   QtGui.QColor("#0000FF"), #Blue
                                   QtGui.QColor("#006400"), #DarkGreen
                                   QtGui.QColor("#9932CC"), #DarkOrchid
                                   QtGui.QColor("#FFA500"), #Orange
                                   QtGui.QColor("#DC143C"), #Crimson
                                   QtGui.QColor("#00008B"), #DarkBlue
                                   QtGui.QColor("#556B2F"), #DarkOLiveGreen
                                   QtGui.QColor("#FF00FF"), #Magenta
                                   QtGui.QColor("#FFD700"), #Gold
                                   ]
        self.dictCurves = {} # {"name" : {'curve': , 'x': , 'y':, 'color', 'show'}, ... }
        self.colorIndex = 0
        self.plot.setLabel('bottom', 'Position/Energy')        
        self.menu = self.plot.getMenu()
        self.autoScale = QtGui.QAction("Auto Scale", self.menu)
        self.autoScale.triggered.connect(self.setAutoScale)
        self.menu.addAction(self.autoScale)
        
        self.buttons = {}
        self.buttonsLayout = QtGui.QHBoxLayout()  
        
        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(self.buttonsLayout)
        self.layout.addWidget(self.plot)
        
        self.setLayout(self.layout)
        
    def setAutoScale(self):
        self.plot.enableAutoRange("x", True)
        self.plot.enableAutoRange("y", True)
        
    def refreshButtons(self):
        #remove
        for bkey in self.buttons.keys():
            self.buttonsLayout.removeWidget(self.buttons[bkey])
            del self.buttons[bkey]
        #add
        for ckey in reversed(self.dictCurves.keys()):
            color = self.dictCurves[ckey]['color'].name()
            self.buttons[ckey] = QtGui.QPushButton(ckey)
            self.buttons[ckey].setStyleSheet("outline: none; color:" + color)
            self.buttons[ckey].setCheckable(True)
            self.buttons[ckey].setChecked(True)
#            self.buttons[ckey].setMAx
            self.buttonsLayout.addWidget(self.buttons[ckey])
            self.buttons[ckey].clicked.connect(self.toggleButton)
#            print ckey
            
    def toggleButton(self):
        bkey = self.sender().text()
        self.plot.clear()
        self.dictCurves[bkey]['show'] = not self.dictCurves[bkey]['show']
        for ckey in self.dictCurves.keys():
            if self.dictCurves[ckey]['show']:
                self.dictCurves[ckey]['curve'] = self.plot.plot(
                                                    self.dictCurves[ckey]['x'], 
                                                    self.dictCurves[ckey]['y'],
                                                    pen = self.dictCurves[ckey]['color'])
            else:
                self.dictCurves[ckey]['curve'] = self.plot.plot(
                                                    [], 
                                                    [],
                                                    pen = self.dictCurves[ckey]['color'])
    
    def addData(self, name, x, y, first = False):
        if first:            
            color = self.curveColors[self.colorIndex]
            curve = self.plot.plot([x], [y], pen = color)                   
            self.dictCurves[name] = {'curve': curve,
                                     'color': color,
                                      'show': True,
                                         'x': [x],
                                         'y': [y]}
            self.colorIndex = (self.colorIndex + 1)%len(self.curveColors)
        else:
            self.dictCurves[name]['x'].append(x)
            self.dictCurves[name]['y'].append(y)
            if self.dictCurves[name]['show']: 
                self.dictCurves[name]['curve'].setData(
                                                    self.dictCurves[name]['x'],
                                                    self.dictCurves[name]['y'])
               

class MonitorWidget(QtGui.QTabWidget):

    def __init__(self, *args):
        QtGui.QTabWidget.__init__(self, *args)
        self.isRunning = False         
        self.tab_c = Plot0dWidget()
        self.tab_m = None
        self.plots2d = {}        
        self.addTab(self.tab_c, "Counters")        

    def updateData(self, data):
        
        if self.isRunning: # 2nd, 3rd, 4th ... points
            x = data[0]['pos']
            for i, d in enumerate(data):
                if i == 0:
                    pass
                elif d["type"] == "0d":  
                    self.tab_c.addData(d["name"], x, d["value"])
                elif d["type"] == "mu":  
                    self.tab_m.addData(d["name"], x, d["value"])
                elif d["type"] == "2d":                   
                    self.plots2d[d["name"]].setImage(d["value"])
                                                      
        else: # 1st point
            x = data[0]['pos']
            xlabel = data[0]["name"]
            self.tab_c.plot.setLabel('bottom', xlabel)
            if self.tab_m:
                self.tab_m.plot.setLabel('bottom', xlabel)
            for i, d in enumerate(data):
                if i == 0:
                    pass
                elif d["type"] == "0d":
                    self.tab_c.addData(d["name"], x, d["value"], first = True)
                elif d["type"] == "mu":
                    self.tab_m = Plot0dWidget()
                    self.tab_m.addData(d["name"], x, d["value"], first = True) 
                    self.addTab(self.tab_m, "mu")
                elif d["type"] == "2d":                   
                    self.plots2d[d["name"]] = Plot2dWidget()
                    self.plots2d[d["name"]].setImage(d["value"])
                    self.addTab(self.plots2d[d["name"]], d["name"])       
            self.isRunning = True 
            self.tab_c.refreshButtons()     
            if self.tab_m:
                self.tab_m.refreshButtons()                                
#        self.tab_c.plot.replot()
        
    def clearData(self):
        self.tab_c.dictCurves = {}
        self.tab_c.plot.clear()
        self.clear()
        self.addTab(self.tab_c, "Counters")
        self.tab_c.plot.setLabel('bottom', 'Position/Energy')
        self.tab_c.plot.replot()
        self.tab_c.colorIndex = 0
        self.isRunning = False 