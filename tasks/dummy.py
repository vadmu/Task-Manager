from PyQt4 import QtCore
#from random import randint
from time import sleep
import numpy as np


class DummyGaussScanTaskWorker(QtCore.QObject):
    updateData  = QtCore.pyqtSignal(int, float) 
    finished = QtCore.pyqtSignal()  
    def __init__(self, parent = None):
        QtCore.QObject.__init__(self, parent)  
        self.stopFlag = False
        self.tppList = []
        self.posList = []
    
    def gauss(self, x, c, w):
        return np.exp(-0.5*(x-c)*(x-c)/w/w)
   
    def process(self):
        c = 0.5*(self.posList[0] + self.posList[-1])
        w = 0.05*(self.posList[-1] - self.posList[0])
        for i in range(len(self.posList)):
            while self.stopFlag:
                #waiting 
                sleep(0.001)                                                  
            # work 
            sleep(self.tppList[i])
            v = self.gauss(self.posList[i], c, w)
            self.updateData.emit(i, v)
        self.finished.emit()
    
    @QtCore.pyqtSlot()    
    def stop(self):
        self.stopFlag = True 
    
    @QtCore.pyqtSlot()      
    def resume(self):
        self.stopFlag = False 
        
        
class DummyGaussScanTask(QtCore.QObject):
    taskName = "Dummy Gauss Scan"
    regionsNames = ["Start[mm]", "Stop[mm]", "Step[mm]", "Time[s]"]
#    logicNames = ["AutoStart", "Use NEXUS", "Use Encoder", "Use Imagination", "Long Name Boolean Parameter"]
    '''
    A class for doing a Task
    It has a worker that runs in a separate thread
    '''
    updateProgress = QtCore.pyqtSignal(float)
    updateData = QtCore.pyqtSignal(float, float)
    clearData = QtCore.pyqtSignal()
    finished = QtCore.pyqtSignal()
    isEditable = True
    def __init__(self, name=None, parent = None, 
                 regions = [[100, 200, 2, 0.05],
                            [200, 301, 2, 0.05]],
                 logic = {"Autostart" : True,
                          "Use NEXUS" : False, 
                          "Use Encoder" : False, 
                          "Use Imagination" : True, 
                          "Long Name Boolean Parameter" : False
                          }):
        QtCore.QObject.__init__(self, parent)
        self.name = name
        self.regions = regions
        self.logic = logic    
        
        self.loops = 1
        self.loopCounter = 0 # current loop which is running
        self.progress = 0 
        self.currentPoint = 0

        
        self.isRunning = False
        self.isStopped = False 
        self.isFinished = False  
        self.isEditable = True        
        
        self.taskThread = QtCore.QThread(self) 
        self.taskWorker = DummyGaussScanTaskWorker()                         
        self.taskWorker.moveToThread(self.taskThread)        
        self.taskThread.started.connect(self.taskWorker.process)           
        self.taskWorker.finished.connect(self.taskThread.quit)
        self.taskThread.finished.connect(self.finish)
        self.taskWorker.updateData.connect(self.update)
        
        print self.name + " created"
        self.recalculate()

    
    def recalculate(self):
        self.posList = np.array([])
        self.tppList = np.array([])
        for r in self.regions:
            reg = np.arange(r[0], r[1], r[2])
            self.posList = np.concatenate([self.posList, reg])
            self.tppList = np.concatenate([self.tppList, [r[3]]*len(reg)])                        
        self.stepsTotal = len(self.posList) 
        self.time4loop = sum(self.tppList)
        print self.posList
        print self.tppList
        self.timeTotal = self.time4loop*self.loops  
        if self.timeTotal != 0 and self.loopCounter != 0:
            self.progress = 100.*(sum(self.tppList[:self.currentPoint+1]) + self.time4loop*(self.loopCounter-1))/self.timeTotal
        else:
            self.progress = 0.
        self.updateProgress.emit(self.progress)
        
            
    def start(self):        
        if self.loops > 0:
            if self.isStopped: 
                # Resume
                QtCore.QMetaObject.invokeMethod(self.taskWorker, "resume", QtCore.Qt.DirectConnection)
                print self.name + " resumed"
            else: 
                # Start the worker here
                self.isEditable = False
                self.loopCounter += 1
                self.clearData.emit()
                self.taskWorker.tppList = self.tppList
                self.taskWorker.posList = self.posList
                self.taskThread.start()
                print self.name + " (%d/%d) started"%(self.loopCounter, self.loops)   
                
            self.isStopped = False
            self.isRunning = True
        else:
            print self.name + " skipped" 
            self.progress = 100.
            self.timeTotal = 0.
            self.isStopped = False
            self.isRunning = False
            self.isFinished = True
            self.finished.emit()
        
    def setLoops(self, value): 
        if value > self.loopCounter:            
            self.loops = value
        elif self.isRunning or self.isStopped:
            self.loops = self.loopCounter
        else:
            self.loops = value
#        if (not self.isFinished) and (self.loops):  
#            self.loops = value
        self.recalculate() 
        
    def stop(self):
        # using DirectConnection to invoke a method in another thread
        # note sure how safe it is but it works
        # SLOT should be seen in QT META OBJECT SPACE 
        # therefore, @QtCore.pyqtSlot() macro should be used on the method
        QtCore.QMetaObject.invokeMethod(self.taskWorker, "stop", QtCore.Qt.DirectConnection)
        self.isStopped = True
        self.isRunning = False
    
    def update(self, i, v):    
        self.currentPoint = i
        self.progress = 100.*(sum(self.tppList[:i+1]) + self.time4loop*(self.loopCounter-1))/self.timeTotal
        self.updateProgress.emit(self.progress)
        self.updateData.emit(self.posList[i], v)
        
    def finish(self):
        if self.loopCounter < self.loops:
            self.start()
        else:
            print self.name + " finished"        
            self.isStopped = False
            self.isRunning = False
            self.isFinished = True
            self.isEditable = True
            self.finished.emit()

            
            
            
            
KTOE = 3.8099819442818976 # 1.e20*hbar**2 / (2.*m_e * e), was taken from Larch 
def etok(energy):
    """convert photo-electron energy to wavenumber"""
    return np.sqrt(energy/KTOE)

def ktoe(k):
    """convert photo-electron wavenumber to energy"""
    return k*k*KTOE

            
            
class DummyEXAFSScanTaskWorker(QtCore.QObject):
    updateData  = QtCore.pyqtSignal(int, float) 
    finished = QtCore.pyqtSignal()  
    def __init__(self, parent = None):
        QtCore.QObject.__init__(self, parent)  
        self.stopFlag = False
        self.tppList = []
        self.posList = []
        self.e0 = 8979.
    
    def exafsCu(self, e, e0):
        if e > e0:
            exafs = np.sin(e-e0)/(e-e0)
        else:
            exafs = 0
        return 1./(1 + np.exp(-(e-e0)/0.125)) - 1e-4*e + exafs
   
    def process(self):
        for i in range(len(self.posList)):
            while self.stopFlag:
                #waiting 
                sleep(0.001)                                                  
            # work 
            sleep(self.tppList[i])
            v = self.exafsCu(self.posList[i], self.e0)
            self.updateData.emit(i, v)
        self.finished.emit()
    
    @QtCore.pyqtSlot()    
    def stop(self):
        self.stopFlag = True 
    
    @QtCore.pyqtSlot()      
    def resume(self):
        self.stopFlag = False 
        
        
class DummyEXAFSTask(QtCore.QObject):
    taskName = "Dummy EXAFS Scan"
    regionsNames = ["Edge[eV]", "Start[eV]", "Step[eV|A-1]", "Time[s]", "Power"]
#    logicNames = ["AutoStart", "Use NEXUS", "Use Encoder", "Use Imagination", "Long Name Boolean Parameter"]
    '''
    A class for doing a Task
    It has a worker that runs in a separate thread
    '''
    updateProgress = QtCore.pyqtSignal(float)
    updateData = QtCore.pyqtSignal(float, float)
    clearData = QtCore.pyqtSignal()
    finished = QtCore.pyqtSignal()
    isEditable = True
    def __init__(self, name=None, parent=None, 
                 regions = [[8979, -200, 10, 0.5], 
                            [8979, -50, 1, 0.5], 
                            [8979, -30, 0.2, 0.5], 
                            [8979, 50, 1, 0.5],                            
                            [8979, 100, 0.05, 0.5, 1], 
                            [8979, 1200]], 
                 logic = {"Autostart" : True,
                          "Use NEXUS" : False, 
                          "Use Encoder" : False, 
                          "Use Imagination" : True, 
                          "Long Name Boolean Parameter" : False
                          }):
        QtCore.QObject.__init__(self, parent)
        self.name = name
        self.regions = regions
        self.logic = logic    
        
        self.loops = 1
        self.loopCounter = 0 # current loop which is running
        self.progress = 0 
        self.currentPoint = 0
        
        self.isRunning = False
        self.isStopped = False 
        self.isFinished = False  
        self.isEditable = True        
        
        self.taskThread = QtCore.QThread(self) 
        self.taskWorker = DummyEXAFSScanTaskWorker()                         
        self.taskWorker.moveToThread(self.taskThread)        
        self.taskThread.started.connect(self.taskWorker.process)           
        self.taskWorker.finished.connect(self.taskThread.quit)
        self.taskThread.finished.connect(self.finish)
        self.taskWorker.updateData.connect(self.update)
        
        print self.name + " created"
        self.recalculate()

        
    def recalculate(self):
        self.posList = np.array([])
        self.tppList = np.array([])
        for i, r in enumerate(self.regions):
            if len(r) == 4:
                newE = np.arange(r[1] + r[0], self.regions[i+1][1] + self.regions[i+1][0], r[2])
                self.posList = np.concatenate([self.posList, newE])
                self.tppList = np.concatenate([self.tppList, [r[3]]*len(newE)])    
            elif len(r) == 5:    
                newk = np.arange(etok(r[1]), etok(self.regions[i+1][1]), r[2])
                newE = ktoe(newk) + r[0]
                self.posList = np.concatenate([self.posList, newE])
                self.tppList = np.concatenate([self.tppList, r[3]*(newk/newk[0])**r[4]])                
            
        self.stepsTotal = len(self.posList) 
        self.time4loop = sum(self.tppList)
        print self.posList
        print self.tppList
        self.timeTotal = self.time4loop*self.loops  
        if self.timeTotal != 0 and self.loopCounter != 0:
            self.progress = 100.*(sum(self.tppList[:self.currentPoint+1]) + self.time4loop*(self.loopCounter-1))/self.timeTotal
        else:
            self.progress = 0.
        self.updateProgress.emit(self.progress)
        
            
    def start(self):        
        if self.loops > 0:
            if self.isStopped: 
                # Resume
                QtCore.QMetaObject.invokeMethod(self.taskWorker, "resume", QtCore.Qt.DirectConnection)
                print self.name + " resumed"
            else: 
                # Start the worker here
                self.isEditable = False
                self.loopCounter += 1
                self.clearData.emit()
                self.taskWorker.tppList = self.tppList
                self.taskWorker.posList = self.posList
                self.taskThread.start()
                print self.name + " (%d/%d) started"%(self.loopCounter, self.loops)   
                
            self.isStopped = False
            self.isRunning = True
        else:
            print self.name + " skipped" 
            self.progress = 100.
            self.timeTotal = 0.
            self.isStopped = False
            self.isRunning = False
            self.isFinished = True
            self.finished.emit()
        
    def setLoops(self, value): 
        if value > self.loopCounter:            
            self.loops = value
        elif self.isRunning or self.isStopped:
            self.loops = self.loopCounter
        else:
            self.loops = value
#        if (not self.isFinished) and (self.loops):  
#            self.loops = value
        self.recalculate() 
        
    def stop(self):
        # using DirectConnection to invoke a method in another thread
        # note sure how safe it is but it works
        # SLOT should be seen in QT META OBJECT SPACE 
        # therefore, @QtCore.pyqtSlot() macro should be used on the method
        QtCore.QMetaObject.invokeMethod(self.taskWorker, "stop", QtCore.Qt.DirectConnection)
        self.isStopped = True
        self.isRunning = False
    
    def update(self, i, v):    
        self.currentPoint = i
        self.progress = 100.*(sum(self.tppList[:i+1]) + self.time4loop*(self.loopCounter-1))/self.timeTotal
        self.updateProgress.emit(self.progress)
        self.updateData.emit(self.posList[i], v)
        
    def finish(self):
        if self.loopCounter < self.loops:
            self.start()
        else:
            print self.name + " finished"        
            self.isStopped = False
            self.isRunning = False
            self.isFinished = True
            self.isEditable = True
            self.finished.emit()