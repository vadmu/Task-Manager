#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
"""
@author: VM
"""
import sys
import numpy as np
from PyQt4 import QtGui, QtCore
from tasks.dummy import DummyGaussScanTask, DummyEXAFSTask
from tasks.stepscan import StepScanTask
from tasks.stepscan_test import EnergyStepScanTask
from tasks.contscan import ContScanTask
from inspect import getargspec, isclass
#from monitor.MonitorWidget import MonitorWidget
#from monitor.MonitorWidgetQwt import MonitorWidget
from monitor.MonitorWidgetPQG import MonitorWidget
import logging

tasksAvailable = [DummyGaussScanTask, DummyEXAFSTask, ContScanTask, StepScanTask, EnergyStepScanTask]

PROGRESS_COLUMN_INDEX = 3
LOOP_COLUMN_INDEX = 2
NAME_COLUMN_INDEX = 1


#from PyQt4.QtCore import QT_VERSION_STR
#from PyQt4.pyqtconfig import Configuration
#print("Qt version:", QT_VERSION_STR)
#cfg = Configuration()
#print("SIP version:", cfg.sip_version_str)
#print("PyQt version:", cfg.pyqt_version_str)
#print (sys.version) 

# make logger
logging.basicConfig(format ='%(levelname)-8s [%(asctime)-15s] %(message)s', 
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level = logging.DEBUG,
                    filename = 'testlog.log')

console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)-8s [%(asctime)-15s] %(message)s')
formatter.datefmt = '%Y-%m-%d %H:%M:%S'
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

def sectoHHMMSS(sec):
    h = int(sec/3600)
    m = int((sec - 3600*h)/60)
    s = round(sec - 3600*h - 60*m) 
    return "%02d:%02d:%02d"%(h, m, s)

                
class TaskTableModel(QtCore.QAbstractTableModel):
    '''
    Model for the tasks
    '''
    updateTotalProgress = QtCore.pyqtSignal(float)
    updateTimeLeft = QtCore.pyqtSignal(float)
    pauseTask = QtCore.pyqtSignal()
    startTask = QtCore.pyqtSignal()
    tasksFinished = QtCore.pyqtSignal()
    def __init__(self, parent = None, plotter = None):
        QtCore.QAbstractTableModel.__init__(self, parent)
        self.taskList = []                  
        self.currentTask = 0
        self.isRunning = False
        self.isPaused = False
        self.isFinished = False
        self.headerNames = ["Icon", "Task Name", "Loops", "Progress", "Time [hh:mm:ss]", "Status"]       
        self.plotter = plotter                       
                                     
    def rowCount(self, parent):
        return len(self.taskList)
        
    def columnCount(self, parent):
        return 6
        
    def data(self, index, role):
        if role == QtCore.Qt.DisplayRole:  
            task = self.taskList[index.row()]
            if index.column() == NAME_COLUMN_INDEX:                   
                return task.name  
            elif index.column() == LOOP_COLUMN_INDEX:
                return task.loops   
            elif index.column() == PROGRESS_COLUMN_INDEX:                   
                return task.progress  
            elif index.column() == 4:                   
                return sectoHHMMSS(task.timeTotal) 
            elif index.column() == 5:   
                if task.isRunning:
                    return "running %d of %d"%(task.loopCounter, task.loops)
                elif task.isPaused:
                    return "paused %d of %d"%(task.loopCounter, task.loops)
                elif task.isFinished:
                    if task.loops == 0:
                        return "skipped"
                    else:
                        return "finished %d of %d"%(task.loopCounter, task.loops)
                elif task.logic["Autostart"]:
                    if task.loops == 0:
                        return "skipped"
                    else:
                        return "autostart"
                else:
                    return "wait"
            else:
                return None
                
        if role == QtCore.Qt.EditRole:
            task = self.taskList[index.row()]
            if index.column() == LOOP_COLUMN_INDEX:
                return task.loops   
    
    def headerData(self, sect, orient, role):
        if (role == QtCore.Qt.DisplayRole) and (orient == QtCore.Qt.Horizontal):
            return self.headerNames[sect]
        if (role == QtCore.Qt.DisplayRole) and (orient == QtCore.Qt.Vertical):
            return sect + 1
                
    def setData(self, index, value, role):
        if role == QtCore.Qt.EditRole:
            task = self.taskList[index.row()]
            if index.column() == LOOP_COLUMN_INDEX:
                task.setLoops(value)
                self.updateTask()
                return True
            elif index.column() == NAME_COLUMN_INDEX:
                if value:
                    task.name = str(value)
        return False
            
    def addTask(self, name, taskType, regions, logic):
        if self.taskList:
#            self.taskList.append(eval(taskType)(name, regions = regions, logic = logic))
            self.taskList.append(taskType(name, regions = regions, logic = logic))
            self.layoutChanged.emit()
        else:
#            self.taskList.append(eval(taskType)(name, regions = regions, logic = logic))
            self.taskList.append(taskType(name, regions = regions, logic = logic))
            self.taskList[0].finished.connect(self.startNext)
            self.taskList[0].updateProgress.connect(self.updateTask)
            self.taskList[0].updateData.connect(self.plotter.updateData)
            self.taskList[0].clearData.connect(self.plotter.clearData)
            self.layoutChanged.emit()  
        logging.getLogger('').debug(taskType.taskName + " <" + name + "> added to model")
        self.updateTask()
            
    def removeTask(self, taskIndex):
        if self.currentTask == 0:
            self.taskList[0].updateProgress.disconnect(self.updateTask)
            self.taskList[0].updateData.connect(self.plotter.updateData)
            self.taskList[0].clearData.connect(self.plotter.clearData)
            self.taskList[0].finished.disconnect(self.startNext)
        logging.getLogger('').debug(self.taskList[taskIndex].taskName + " <" + self.taskList[taskIndex].name + "> removed from model")    
        del self.taskList[taskIndex]
        if self.taskList:
            self.taskList[0].finished.connect(self.startNext)
            self.taskList[0].updateProgress.connect(self.updateTask) 
            self.taskList[0].updateData.connect(self.plotter.updateData)   
            self.taskList[0].clearData.connect(self.plotter.clearData)            
        if taskIndex < self.currentTask:
            self.currentTask -= 1        
        self.layoutChanged.emit() 
        self.updateTask()
    
    def copyTask(self, taskIndex):
        name = self.taskList[taskIndex].name + " (Copy)"
        regions = [list(v) for v in self.taskList[taskIndex].regions] # copy of the data not the pointer
        logic = self.taskList[taskIndex].logic.copy()
        self.taskList.append(type(self.taskList[taskIndex])(name, regions = regions, logic = logic))
        self.layoutChanged.emit()
        logging.getLogger('').debug(self.taskList[taskIndex].taskName + " <" + name + "> copied in model")
        self.updateTask()
        
                
    def updateTask(self):
        i = self.currentTask
        self.dataChanged.emit(self.index(i, 3), self.index(i, 5))    
        num = sum([t.progress*t.timeTotal for t in self.taskList])
        denom = sum([t.timeTotal for t in self.taskList])
        with np.errstate(divide='ignore', invalid='ignore'):
            totalProgress = np.divide(num, denom)   
            if not np.isfinite( totalProgress ):# -inf inf NaN
                totalProgress = 0  
        self.updateTotalProgress.emit(totalProgress)
        timeLeft = denom * (1. - 0.01*totalProgress)
        self.updateTimeLeft.emit(timeLeft)
    
            
    def start(self):
        self.isRunning = True    
        self.isPaused = False
        if self.currentTask < len(self.taskList):
            if self.isFinished:
                self.isFinished = False
                self.taskList[self.currentTask].finished.connect(self.startNext)
                self.taskList[self.currentTask].updateProgress.connect(self.updateTask)
                self.taskList[self.currentTask].updateData.connect(self.plotter.updateData)
                self.taskList[self.currentTask].clearData.connect(self.plotter.clearData)
                self.taskList[self.currentTask].start()                
            else:
                self.taskList[self.currentTask].start()
        else:
            self.isFinished = False  
            for task in self.taskList:
                task.isFinished = False
                task.progress = 0.0   
                task.loopCounter = 0
            self.currentTask = 0
            if self.taskList:            
                self.taskList[0].finished.connect(self.startNext)
                self.taskList[0].updateProgress.connect(self.updateTask)
                self.taskList[0].updateData.connect(self.plotter.updateData) 
                self.taskList[0].clearData.connect(self.plotter.clearData)
                self.taskList[0].start()
                  
            
    def startNext(self):
        self.updateTask()
        self.taskList[self.currentTask].updateProgress.disconnect(self.updateTask)
        self.taskList[self.currentTask].updateData.disconnect(self.plotter.updateData)
        self.taskList[self.currentTask].clearData.disconnect(self.plotter.clearData)
        self.taskList[self.currentTask].finished.disconnect(self.startNext)
        self.currentTask += 1        
        if self.currentTask < len(self.taskList): 
            if self.taskList[self.currentTask].logic["Autostart"]: 
                self.taskList[self.currentTask].finished.connect(self.startNext)
                self.taskList[self.currentTask].updateProgress.connect(self.updateTask)
                self.taskList[self.currentTask].updateData.connect(self.plotter.updateData)
                self.taskList[self.currentTask].clearData.connect(self.plotter.clearData)
                self.plotter.clearData()
                self.taskList[self.currentTask].start()
            else:
                self.isPaused = True
                self.isRunning = False
                self.taskList[self.currentTask].finished.connect(self.startNext)
                self.taskList[self.currentTask].updateProgress.connect(self.updateTask)
                self.taskList[self.currentTask].updateData.connect(self.plotter.updateData)
                self.taskList[self.currentTask].clearData.connect(self.plotter.clearData)
                self.tasksFinished.emit() 
        else:            
            self.finish()
            
                
    def pause(self):  
#        print self.currentTask
        self.isPaused = True
        self.isRunning = False
        if self.currentTask < len(self.taskList):
            self.taskList[self.currentTask].pause()  
        # special hack for continuous scans
        if not self.taskList[self.currentTask].isPaused:
            self.isPaused = False
            self.isRunning = True
        

    def finish(self):
        self.isRunning = False
        self.isPaused = False
        self.isFinished = True
        self.tasksFinished.emit()     
        logging.getLogger('').info("All tasks finished")  
    
    def flags(self, index):
        if (index.column() == LOOP_COLUMN_INDEX) or (index.column() == NAME_COLUMN_INDEX):
            return QtCore.Qt.ItemIsSelectable |  QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled
        else:
            return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
            
#class TaskConfigTable

            
class ProgressDelegate(QtGui.QStyledItemDelegate):
    '''
    A progress bar item for the table view 
    '''        
    def __init__(self, parent):
        QtGui.QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
#        if (index.column() == PROGRESS_COLUMN_INDEX):
#            progress = type(index.data())
        if type(index.data()) == QtCore.QVariant:
            progress = index.data().toPyObject()
        else:
            progress = index.data()
        progressBarOption = QtGui.QStyleOptionProgressBar()
        progressBarOption.rect = option.rect
        progressBarOption.minimum = 0
        progressBarOption.maximum = 100
        progressBarOption.progress = progress
        progressBarOption.text = "%.2f%%"%progress
#            progressBarOption.text = "%d%%"%progress
        progressBarOption.textVisible = True            
        QtGui.QApplication.style().drawControl(QtGui.QStyle.CE_ProgressBar, progressBarOption, painter)
#        else:
#            QtGui.QStyledItemDelegate.paint(painter, option, index)


class SpinBoxDelegate(QtGui.QStyledItemDelegate):
    def __init__(self, parent):
        QtGui.QStyledItemDelegate.__init__(self, parent)
        
    def createEditor(self, parent, option, index):
        editor = QtGui.QSpinBox(parent)
        editor.setFrame(False)
        editor.setMinimum(0)
        editor.setMaximum(100)
        return editor
#
    def setEditorData(self, spinBox, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        spinBox.setValue(value)

    def setModelData(self, spinBox, model, index):
        spinBox.interpretText()
        value = spinBox.value()
        model.setData(index, value, QtCore.Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

        
class NumberFormatDelegate(QtGui.QStyledItemDelegate):
    def __init__(self, parent):
        QtGui.QStyledItemDelegate.__init__(self, parent)
        
    def createEditor(self, parent, option, index):
        editor = QtGui.QLineEdit(parent)
        validator  = QtGui.QDoubleValidator()
        editor.setValidator(validator)
        return editor
#
    def setEditorData(self, lineEdit, index):
        value = index.model().data(index, QtCore.Qt.DisplayRole)
        lineEdit.setText(str(value))
#
    def setModelData(self, lineEdit, model, index):
#        lineEdit.interpretText()
        value = lineEdit.text()
        try:
           value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                value = None
        model.setData(index, value, QtCore.Qt.EditRole)
#
    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)         
        
        
class ConfigRegionsModel(QtCore.QAbstractTableModel):
    def __init__(self, parent = None):
        QtCore.QAbstractTableModel.__init__(self, parent)
        self.task = []
        self.regions = []
        self.regionsNames = [] 

    def change(self, taskType, newTask):
        if newTask:
            # class only
            self.task = taskType
            self.regions = [list(v) for v in getargspec(self.task.__init__)[3][2][:]]
            self.regionsNames = self.task.regionsNames[:]
        elif taskType != None:
            # edit task
            self.task = taskType
            self.regions = self.task.regions
            self.regionsNames = self.task.regionsNames[:]
        else:
            self.task = []
            self.regions = []
            self.regionsNames = []
        self.layoutChanged.emit()
        
    def rowCount(self, parent):
        return len(self.regions)
        
    def columnCount(self, parent):
        return len(self.regionsNames)
    
    def data(self, index, role):
        if role == QtCore.Qt.DisplayRole:  
#            if index.column() < len(self.regions[index.row()]):
            return self.regions[index.row()][index.column()]

    def headerData(self, sect, orient, role):
        if (role == QtCore.Qt.DisplayRole) and (orient == QtCore.Qt.Horizontal):
            return self.regionsNames[sect]
    
    def setData(self, index, value, role):
        if role == QtCore.Qt.EditRole:
#            if index.column() < len(self.regions[index.row()]):
            self.regions[index.row()][index.column()] = value            
            if not isclass(self.task):
                self.task.recalculate()
            self.layoutChanged.emit()
            self.dataChanged.emit(index, index) 
#            
            return True
        return False   

    def addEmptyRegion(self):
        self.regions.append([None]*len(self.regionsNames))
        self.layoutChanged.emit()
        
    def flags(self, index):
        if isclass(self.task):
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable
        elif self.task.isEditable:
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable     
        else:
            return QtCore.Qt.ItemIsEnabled                 
                                    
class ConfigLogicModel(QtCore.QAbstractListModel):
    def __init__(self, parent = None):
        QtCore.QAbstractListModel.__init__(self, parent)
        self.task = None
        self.logic = {}
        self.logicNames = []
             
    def change(self, taskType, newTask):
        if newTask:
            self.task = taskType
            self.logic = (getargspec(self.task.__init__)[3][3]).copy() # default will be preserved
            self.logicNames = sorted(self.logic.keys())
            self.editable = True
        elif taskType != None:
            self.task = taskType
            self.logic = self.task.logic
            self.logicNames = sorted(self.task.logic.keys())
        else:
            self.task = None
            self.logic = {}
            self.logicNames = [] 
        self.layoutChanged.emit()
        
        
    def rowCount(self, parent):
        return len(self.logic)
        
    def columnCount(self, parent):
        return 1
    
    def data(self, index, role):
        if role == QtCore.Qt.DisplayRole:
            if index.column() == 0:     
                return self.logicNames[index.row()] 
        if role == QtCore.Qt.CheckStateRole:
            if index.column() == 0:     
                # 0 - unchecked
                # 1 - partially checked
                # 2 - fully checked
                key = self.logicNames[index.row()] 
                return 2*self.logic[key]  
    
    def setData(self, index, value, role):
        if role == QtCore.Qt.CheckStateRole:
            if index.column() == 0:
                key = self.logicNames[index.row()] 
                self.logic[key] = bool(value/2)
                self.dataChanged.emit(index, index)
                if not isclass(self.task):
                    self.task.recalculate()
                return True
        return False
                                                                        
    def flags(self, index):
        if (index.column() == 0) and (self.task.isEditable):
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable
        else:
            return QtCore.Qt.ItemIsEnabled
                

class TaskConfig(QtGui.QWidget):   
    def __init__(self, parent = None):
        QtGui.QWidget.__init__(self, parent)
        self.regionsTable = QtGui.QTableView()
        self.logicList = QtGui.QListView()
        self.regionsTable.setSelectionMode(QtGui.QAbstractItemView.SingleSelection) 
        self.regionsTable.setItemDelegate(NumberFormatDelegate(self.regionsTable))
#        self.regionsTable.horizontalHeader().setResizeMode(QtGui.QHeaderView.ResizeToContents)
        self.regionsTable.horizontalHeader().setResizeMode(QtGui.QHeaderView.Stretch)
 
        self.regionsModel = ConfigRegionsModel()
        self.logicModel = ConfigLogicModel()
        self.regionsTable.setModel(self.regionsModel)
        self.logicList.setModel(self.logicModel) 
        self.btnAddRegion = QtGui.QPushButton("Add Region")
        self.setupLayout() 
        self.btnAddRegion.clicked.connect(self.regionsModel.addEmptyRegion)       
        
    def setupLayout(self):
        self.layout = QtGui.QGridLayout()
        self.logicList.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Minimum))
#        self.regionsTable.setSizePolicy(sizePolicy)
        label1 = QtGui.QLabel("Logic")
        label2 = QtGui.QLabel("Regions")
        self.layout.addWidget(label1, 0, 0)
        self.layout.addWidget(label2, 0, 1)
        self.layout.addWidget(self.logicList, 1, 0, 2, 1)
        self.layout.addWidget(self.regionsTable, 1, 1)       
        self.layout.addWidget(self.btnAddRegion, 2, 1)  
        self.setLayout(self.layout)
                    
        
class floatProgressBar(QtGui.QProgressBar):
    '''
    A progress bar that shows value in .2f format
    '''
    def __init__(self, parent = None):
        QtGui.QProgressBar.__init__(self, parent)
        self.setRange(0, 10000)
        self.setValue(0)
        self.valueChanged.connect(self.onValueChanged)

    def onValueChanged(self, value):
        self.setFormat('%.2f%%' % (self.prefixFloat/100.))

    def setValue(self, value):
        self.prefixFloat = value
        QtGui.QProgressBar.setValue(self, int(value))
 
        
class MainW(QtGui.QWidget):   
    '''
    Main widget/window
    '''
    def __init__(self, parent = None):
        QtGui.QWidget.__init__(self, parent)  
        self.selected = -1    
        self.setupLayout()
        self.setupConnections() 
        self.setupButtons()              
                              
    def setupLayout(self):
                
        self.plotter = MonitorWidget()
#        self.plotter.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.MinimumExpanding))        
        self.ttModel = TaskTableModel(plotter = self.plotter)        
        self.ttView = QtGui.QTableView()
        self.ttView.setItemDelegateForColumn(PROGRESS_COLUMN_INDEX, ProgressDelegate(self.ttView))
        self.ttView.setItemDelegateForColumn(LOOP_COLUMN_INDEX, SpinBoxDelegate(self.ttView))
        self.ttView.setSelectionMode(QtGui.QAbstractItemView.SingleSelection) 
        self.ttView.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.ttView.horizontalHeader().setResizeMode(QtGui.QHeaderView.Stretch) 
        self.ttView.horizontalHeader().setHighlightSections(False)
        self.ttView.setModel(self.ttModel)
        
        
        self.statusLayout = QtGui.QHBoxLayout()
        self.totalBar = floatProgressBar()  
        self.totalBar.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum))     
        self.timeLeftLabel = QtGui.QLabel("Time left:")
        self.timeLeftLabel.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Maximum))
        self.timeLeftValue = QtGui.QLabel("--:--:--")
        self.timeLeftValue.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Maximum))
        
        self.configLabel = QtGui.QLabel("<center>Task Configuration")        
        self.config = TaskConfig()
        
           
#        self.plotter = QtGui.QLabel("<center>Plotter")
           
        
        self.btnStart = QtGui.QPushButton("Start")
        self.btnPause = QtGui.QPushButton("Pause")
        self.btnAdd = QtGui.QPushButton("Add")
        self.btnCopy = QtGui.QPushButton("Copy")
        self.btnRemove = QtGui.QPushButton("Remove")
        self.btnClear = QtGui.QPushButton("Clear All")
        self.btnLayout = QtGui.QHBoxLayout()
        self.btnLayout.addWidget(self.btnAdd)
        self.btnLayout.addWidget(self.btnCopy)
        self.btnLayout.addWidget(self.btnRemove)
        self.btnLayout.addWidget(self.btnClear)
        self.btnLayout.addWidget(self.btnStart)
        self.btnLayout.addWidget(self.btnPause)
        
        self.btnClear.setDisabled(True)
#        self.btnRemove.setDisabled(True)
#        self.btnCopy.setDisabled(True)
        
        self.layout = QtGui.QGridLayout()
        self.layout.addLayout(self.btnLayout, 0, 0)
        self.layout.addWidget(self.plotter, 0, 1, 4, 1)
        self.layout.addWidget(self.ttView, 1, 0)
        self.layout.addWidget(self.configLabel, 2, 0)
        self.layout.addWidget(self.config, 3, 0)
        self.statusLayout.addWidget(self.totalBar)     
        self.statusLayout.addWidget(self.timeLeftLabel)   
        self.statusLayout.addWidget(self.timeLeftValue)   
        self.layout.addLayout(self.statusLayout, 4, 0, 1, 2)
        self.setLayout(self.layout) 
               
    def setupConnections(self):
        self.btnStart.clicked.connect(self.start) 
        self.btnPause.clicked.connect(self.pause)
        self.btnRemove.clicked.connect(self.removeTask)
        self.btnCopy.clicked.connect(self.copyTask)
        self.btnAdd.clicked.connect(self.startWizard)
        self.ttView.selectionModel().selectionChanged.connect(self.configureTask)
        self.ttModel.updateTotalProgress.connect(self.updateProgressBarState)
        self.ttModel.updateTimeLeft.connect(self.updateTimeLeftState)
        self.ttModel.tasksFinished.connect(self.setupButtons)
        self.config.regionsModel.dataChanged.connect(self.ttModel.updateTask)
        self.config.logicModel.dataChanged.connect(self.ttModel.updateTask)

        
    def start(self):                
        self.ttModel.start()
        self.setupButtons()        
    
    def pause(self):    
        self.ttModel.pause()
        self.setupButtons()
    
    def setupButtons(self):
#        print self.ttModel.isRunning, self.ttModel.isPaused, self.ttModel.isFinished
#        print self.selected, self.ttModel.currentTask

        if self.ttModel.isRunning:
            # Process is running
            self.btnStart.setText("Running...")
            self.btnStart.setDisabled(True)
            self.btnPause.setText("Pause")
            self.btnPause.setEnabled(True)
            if self.selected == -1:
                self.btnCopy.setDisabled(True)
            else:
                self.btnCopy.setEnabled(True)
            if (self.selected == self.ttModel.currentTask) or (self.selected == -1) :
                self.btnRemove.setDisabled(True)
            else:
                self.btnRemove.setEnabled(True)
                
        elif self.ttModel.isPaused:   
            # Process is paused
            self.btnStart.setText("Continue")
            self.btnStart.setEnabled(True)
            self.btnPause.setText("Paused")
            self.btnPause.setDisabled(True)
            if self.selected == -1:
                self.btnCopy.setDisabled(True)
            else:
                self.btnCopy.setEnabled(True)
            if (self.selected == self.ttModel.currentTask) or (self.selected == -1):
                self.btnRemove.setDisabled(True)
            else:
                self.btnRemove.setEnabled(True)
                
        elif not self.ttModel.taskList:
            # There are no tasks
            self.btnStart.setText("Start")
            self.btnStart.setDisabled(True)
            self.btnPause.setDisabled(True)
            self.btnRemove.setDisabled(True)
            self.btnCopy.setDisabled(True)
            self.config.logicModel.change(taskType = None, newTask = False)
            self.config.regionsModel.change(taskType = None, newTask = False)
            
        elif self.ttModel.isFinished: 
            # All tasks finished
            self.btnStart.setText("Start")
            self.btnStart.setEnabled(True)
            self.btnPause.setDisabled(True)
            if self.selected == -1:
                self.btnRemove.setDisabled(True)
                self.btnCopy.setDisabled(True)
            else:
                self.btnRemove.setEnabled(True)
                self.btnCopy.setEnabled(True)
                              
        else:
            # There are tasks, waiting for start
            self.btnStart.setText("Start")
            self.btnStart.setEnabled(True)
            self.btnPause.setDisabled(True)
            if self.selected == -1:
                self.btnRemove.setDisabled(True)
                self.btnCopy.setDisabled(True)
            else:
                self.btnRemove.setEnabled(True)
                self.btnCopy.setEnabled(True)
            
            
    def startWizard(self): 
        self.dialogWizard = QtGui.QWizard(self) # Modal windows must have a parent!
        self.dialogWizard.setWindowTitle("Experiment Wizard")
        
        ### Page 1 ###
        
        page1 = QtGui.QWizardPage()
        page1.setTitle("Introduction")
        label1a = QtGui.QLabel("\nThis wizard will help you to make your experiment. \n\n" + 
                              "Please, check your inputs twice! " )
        label1a.setWordWrap(True)
        layout1 = QtGui.QVBoxLayout()
        layout1.addWidget(label1a)
        page1.setLayout(layout1)
        
        ### Page 2 ###
        
        page2 = QtGui.QWizardPage()
        page2.setTitle("Add Task")
        label2a = QtGui.QLabel("Select the task name:")        
        label2a.setWordWrap(True)
        layout2 = QtGui.QVBoxLayout()
        layout2.addWidget(label2a)
        newName = "New Task"
        names = [t.name for t in self.ttModel.taskList]
        if newName in names:
            suffix = 1
            while newName in names:
                suffix +=1
                newName = "New Task %d"%suffix
            
        self.line = QtGui.QLineEdit(newName)
        layout2.addWidget(self.line)
        label2b = QtGui.QLabel("Select the task type:") 
        layout2.addWidget(label2b)
        self.vBox = QtGui.QVBoxLayout()
        self.btnGroup = QtGui.QButtonGroup()
        for task in tasksAvailable:
#            btn = QtGui.QRadioButton(eval(task).taskName)
            btn = QtGui.QRadioButton(task.taskName)
            self.btnGroup.addButton(btn)
            self.vBox.addWidget(btn)
        if tasksAvailable:
            self.btnGroup.buttons()[0].setChecked(True)
        layout2.addLayout(self.vBox) 
        page2.setLayout(layout2)
        page2.completeChanged.connect(self.configureTask)
        
        ### Page 3 ###
        
        page3 = QtGui.QWizardPage()
        layout3 = QtGui.QVBoxLayout()
        label3a = QtGui.QLabel("Configure the task:") 
        layout3.addWidget(label3a)
        self.config3 = TaskConfig()
        layout3.addWidget(self.config3)
        page3.setLayout(layout3)
        page3.setMinimumSize(800, 400) 
#        page3.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Minimum))       
        
        self.dialogWizard.addPage(page1)
        self.dialogWizard.addPage(page2)
        self.dialogWizard.addPage(page3)
        self.dialogWizard.accepted.connect(self.addNewTask)    
        self.dialogWizard.currentIdChanged.connect(self.configureNewTask)
        self.dialogWizard.exec_()  
    
    def configureNewTask(self):
        if self.dialogWizard.currentId() == 2:
            self.config3.regionsModel.change(taskType=tasksAvailable[-self.btnGroup.checkedId()-2], newTask = True)
            self.config3.logicModel.change(taskType=tasksAvailable[-self.btnGroup.checkedId()-2], newTask = True)
    
    def configureTask(self, sel, desel):
        if sel.indexes():
            self.selected = sel.indexes()[0].row()   
            self.config.regionsModel.change(taskType = self.ttModel.taskList[self.selected], newTask = False)
            self.config.logicModel.change(taskType = self.ttModel.taskList[self.selected], newTask = False)
        self.setupButtons()
            
    def addNewTask(self):
        # assigned buttons ids are guaranteed to be negative, starting with -2
        # according to documentation: http://doc.qt.io/qt-4.8/qbuttongroup.html#id
        self.ttModel.addTask(self.line.text(), taskType=tasksAvailable[-self.btnGroup.checkedId()-2],
                             regions = self.config3.regionsModel.regions,
                             logic = self.config3.logicModel.logic)       
        self.setupButtons()
    
    def removeTask(self):
        self.ttModel.removeTask(self.selected)        
        self.selected = -1
        self.ttView.clearSelection()
        self.setupButtons()
        
    def copyTask(self):       
        self.ttModel.copyTask(self.selected)  
        self.setupButtons()    
        
    def updateProgressBarState(self, progress):
        self.totalBar.setValue(100.*progress) 
    
    def updateTimeLeftState(self, timeLeft):
        self.timeLeftValue.setText(sectoHHMMSS(timeLeft)) 
        
            
     
app = QtGui.QApplication(sys.argv)

mw = MainW()
mw.setAttribute(QtCore.Qt.WA_DeleteOnClose) # QObject::startTimer: QTimer can only be used with threads started with QThread
mw.setWindowTitle('Task Manager')
mw.setMinimumSize(800, 600)   
mw.setGeometry(100, 50, 1600, 900)
mw.show()
sys.exit(app.exec_())
