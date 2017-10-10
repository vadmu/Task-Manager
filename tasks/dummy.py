from PyQt4 import QtCore
from time import sleep
import numpy as np
import logging


class DummyGaussScanTaskWorker(QtCore.QObject):
    updateData  = QtCore.pyqtSignal(int, float) 
    finished = QtCore.pyqtSignal()  
    def __init__(self, parent = None):
        QtCore.QObject.__init__(self, parent)  
        self.pauseFlag = False
        self.tppList = []
        self.posList = []
    
    def gauss(self, x, c, w):
        return np.exp(-0.5*(x-c)*(x-c)/w/w)
   
    def process(self):
        c = 0.5*(self.posList[0] + self.posList[-1])
        w = 0.05*(self.posList[-1] - self.posList[0])
        for i in range(len(self.posList)):
            while self.pauseFlag:
                #waiting 
                sleep(0.001)                                                  
            # work 
            sleep(self.tppList[i])
            v = self.gauss(self.posList[i], c, w)
            self.updateData.emit(i, v)
        self.finished.emit()
    
    @QtCore.pyqtSlot()    
    def pause(self):
        self.pauseFlag = True 
    
    @QtCore.pyqtSlot()      
    def resume(self):
        self.pauseFlag = False 
        
        
class DummyGaussScanTask(QtCore.QObject):
    taskName = "Dummy Scan"
    regionsNames = ["Start[mm]", "Step[mm]", "Time[s]"]
#    logicNames = ["AutoStart", "Use NEXUS", "Use Encoder", "Use Imagination", "Long Name Boolean Parameter"]
    '''
    A class for doing a Task
    It has a worker that runs in a separate thread
    '''
    updateProgress = QtCore.pyqtSignal(float)
    updateData = QtCore.pyqtSignal(list)
    clearData = QtCore.pyqtSignal()
    finished = QtCore.pyqtSignal()
    isEditable = True
    def __init__(self, name=None, parent = None, 
                 regions = [[100, 2, 0.05],
                            [200, None, None]],
                 logic = {"Autostart" : True,
                          "Save to NEXUS file (*.nxs)" : True,
                          "Save to ASCII file (*.dat)" : True
                          }):
        QtCore.QObject.__init__(self, parent)
        self.name = name
        self.regions = [list(v) for v in regions]
        self.logic = logic    
        
        self.loops = 1
        self.loopCounter = 0 # current loop which is running
        self.progress = 0 
        self.currentPoint = 0

        
        self.isRunning = False
        self.isPaused = False 
        self.isFinished = False  
        self.isEditable = True        
        
        self.taskThread = QtCore.QThread(self) 
        self.taskWorker = DummyGaussScanTaskWorker()                         
        self.taskWorker.moveToThread(self.taskThread)        
        self.taskThread.started.connect(self.taskWorker.process)           
        self.taskWorker.finished.connect(self.taskThread.quit)
        self.taskThread.finished.connect(self.finish)
        self.taskWorker.updateData.connect(self.update)
              
        logging.getLogger('').debug(self.taskName + " <" + self.name + "> created")
        self.recalculate()

    
    def recalculate(self):
        self.posList = np.array([])
        self.tppList = np.array([])
        self.empty = []
        for i, r in enumerate(self.regions):
            if r.count(None) == 3:
                self.empty += [i]
            elif r.count(None) == 0:
                reg = np.arange(r[0], self.regions[i+1][0], r[1])
                self.posList = np.concatenate([self.posList, reg])
                self.tppList = np.concatenate([self.tppList, [r[2]]*len(reg)]) 
        for i in sorted(self.empty, reverse = True):
            del self.regions[i]                     
        self.stepsTotal = len(self.posList) 
        self.time4loop = sum(self.tppList)
        self.timeTotal = self.time4loop*self.loops  
        if self.timeTotal != 0 and self.loopCounter != 0:
            self.progress = 100.*(sum(self.tppList[:self.currentPoint+1]) + self.time4loop*(self.loopCounter-1))/self.timeTotal
#            self.progress = 100.*sum(self.tppList[:self.currentPoint+1])/self.time4loop
        else:
            self.progress = 0.
        self.updateProgress.emit(self.progress)
        logging.getLogger('').debug(self.taskName + " <" + self.name + "> regions: " + str(self.regions) )
        logging.getLogger('').debug(self.taskName + " <" + self.name + "> loops: %d/%d "%(self.loopCounter, self.loops) )
        
            
    def start(self):        
        if self.loops > 0:
            if self.isPaused: 
                # Resume
                QtCore.QMetaObject.invokeMethod(self.taskWorker, "resume", QtCore.Qt.DirectConnection)
                logging.getLogger('').info(self.taskName + " <" + self.name + "> resumed")
            else: 
                # Start the worker here
                self.isEditable = False
                self.loopCounter += 1
                self.clearData.emit()
                self.taskWorker.tppList = self.tppList
                self.taskWorker.posList = self.posList
                self.taskThread.start()
                logging.getLogger('').info(self.taskName + " <" + self.name + "> (%d/%d) started"%(self.loopCounter, self.loops) )  
                
            self.isPaused = False
            self.isRunning = True
        else:
            print self.name + " skipped" 
            self.progress = 100.
            self.timeTotal = 0.
            self.isPaused = False
            self.isRunning = False
            self.isFinished = True
            self.finished.emit()
        
    def setLoops(self, value): 
        if value > self.loopCounter:            
            self.loops = value
        elif self.isRunning or self.isPaused:
            self.loops = self.loopCounter
        else:
            self.loops = value
#        if (not self.isFinished) and (self.loops):  
#            self.loops = value
        self.recalculate() 
        
    def pause(self):
        # using DirectConnection to invoke a method in another thread
        # note sure how safe it is but it works
        # SLOT should be seen in QT META OBJECT SPACE 
        # therefore, @QtCore.pyqtSlot() macro should be used on the method
        QtCore.QMetaObject.invokeMethod(self.taskWorker, "pause", QtCore.Qt.DirectConnection)
        self.isPaused = True
        self.isRunning = False
        logging.getLogger('').debug(self.taskName + " <" + self.name + "> paused")
    
    def update(self, i, v):    
        self.currentPoint = i
        self.progress = 100.*(sum(self.tppList[:i+1]) + self.time4loop*(self.loopCounter-1))/self.timeTotal
#        self.progress = 100.*sum(self.tppList[:i+1])/self.time4loop
        self.updateProgress.emit(self.progress)
        self.updateData.emit([{
                               "name" : "Dummy",
                               "addr" : "*****",
                               "pos"  : self.posList[i]
                              },                               
                              {
                               "name" : "i0",
                               "type" : "0d",
                               "value": v
                              },
                              {
                               "name" : "i1",
                               "type" : "0d",
                               "value": 0.5*v
                              },
                              {
                               "name" : "mu01",
                               "type" : "mu",
                               "value": np.sin(10.*v)
                              },
                              {
                               "name" : "lambda1",
                               "type" : "2d",
                               "value": np.random.randint(1024, size=(1000, 500))
                              }                              
                             ]
                            )
        
    def finish(self):        
        logging.getLogger('').info(self.taskName + " <" + self.name + "> (%d/%d) finished"%(self.loopCounter, self.loops) )  
        if self.loopCounter < self.loops:
            self.start()
        else: 
            self.isPaused = False
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
        self.pauseFlag = False
        self.tppList = []
        self.posList = []
        self.e0 = 8979.
    
    def exafsCu(self, e, e0):
        if e > e0:
            exafs = np.sin(0.5*(e-e0))/(e-e0)
            return 1./(1 + np.exp(-(e-e0)/0.125)) - 1e-4*e + exafs
        else:
            return -1e-4*e
   
    def process(self):
        for i in range(len(self.posList)):
            while self.pauseFlag:
                #waiting 
                sleep(0.001)                                                  
            # work 
            sleep(self.tppList[i])
            v = self.exafsCu(self.posList[i], self.e0)
            self.updateData.emit(i, v)
        self.finished.emit()
    
    @QtCore.pyqtSlot()    
    def pause(self):
        self.pauseFlag = True 
    
    @QtCore.pyqtSlot()      
    def resume(self):
        self.pauseFlag = False 
        
        
class DummyEXAFSTask(QtCore.QObject):
    taskName = "Dummy EXAFS Scan"
    regionsNames = ["Edge[eV]", "Start[eV]", "Step[eV|A-1]", "Time[s]", "Power"]
#    logicNames = ["AutoStart", "Use NEXUS", "Use Encoder", "Use Imagination", "Long Name Boolean Parameter"]
    '''
    A class for doing a Task
    It has a worker that runs in a separate thread
    '''
    updateProgress = QtCore.pyqtSignal(float)
    updateData = QtCore.pyqtSignal(list)
    clearData = QtCore.pyqtSignal()
    finished = QtCore.pyqtSignal()
    isEditable = True
    def __init__(self, name=None, parent=None, 
                 regions = [[8979, -200, 10, 0.05, None], 
                            [8979, -50, 1, 0.05, None], 
                            [8979, -30, 0.2, 0.05, None], 
                            [8979, 50, 1, 0.05, None],                            
                            [8979, 100, 0.05, 0.05, 1], 
                            [8979, 500, None, None, None]], 
                 logic = {"Autostart" : True,
                          "Save to NEXUS file (*.nxs)" : True,
                          "Save to ASCII file (*.dat)" : True,
                          "Move Parallel" : False
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
        self.isPaused = False 
        self.isFinished = False  
        self.isEditable = True        
        
        self.taskThread = QtCore.QThread(self) 
        self.taskWorker = DummyEXAFSScanTaskWorker()                         
        self.taskWorker.moveToThread(self.taskThread)        
        self.taskThread.started.connect(self.taskWorker.process)           
        self.taskWorker.finished.connect(self.taskThread.quit)
        self.taskThread.finished.connect(self.finish)
        self.taskWorker.updateData.connect(self.update)
        
        logging.getLogger('').debug(self.taskName + " <" + self.name + "> created")
        self.recalculate()

        
    def recalculate(self):
        self.posList = np.array([])
        self.tppList = np.array([])
        for i, r in enumerate(self.regions):
            if r.count(None) == 5:
                del self.regions[i]
                continue
            elif r.count(None) == 1:
                newE = np.arange(r[1] + r[0], self.regions[i+1][1] + self.regions[i+1][0], r[2])
                self.posList = np.concatenate([self.posList, newE])
                self.tppList = np.concatenate([self.tppList, [r[3]]*len(newE)])    
            elif r.count(None) == 0:    
                newk = np.arange(etok(r[1]), etok(self.regions[i+1][1]), r[2])
                newE = ktoe(newk) + r[0]
                self.posList = np.concatenate([self.posList, newE])
                self.tppList = np.concatenate([self.tppList, r[3]*(newk/newk[0])**r[4]])                
            
        self.stepsTotal = len(self.posList) 
        self.time4loop = sum(self.tppList)
        self.timeTotal = self.time4loop*self.loops  
        if self.timeTotal != 0 and self.loopCounter != 0:
            self.progress = 100.*(sum(self.tppList[:self.currentPoint+1]) + self.time4loop*(self.loopCounter-1))/self.timeTotal
        else:
            self.progress = 0.
        self.updateProgress.emit(self.progress)
        logging.getLogger('').debug(self.taskName + " <" + self.name + "> regions: " + str(self.regions) )
        logging.getLogger('').debug(self.taskName + " <" + self.name + "> loops: %d/%d "%(self.loopCounter, self.loops) )
        
            
    def start(self):        
        if self.loops > 0:
            if self.isPaused: 
                # Resume
                QtCore.QMetaObject.invokeMethod(self.taskWorker, "resume", QtCore.Qt.DirectConnection)
                logging.getLogger('').debug(self.taskName + " <" + self.name + "> resumed")
            else: 
                # Start the worker here
                self.isEditable = False
                self.loopCounter += 1
                self.clearData.emit()
                self.taskWorker.tppList = self.tppList
                self.taskWorker.posList = self.posList
                self.taskThread.start()
                logging.getLogger('').info(self.taskName + " <" + self.name + "> (%d/%d) started"%(self.loopCounter, self.loops) ) 
                
            self.isPaused = False
            self.isRunning = True
        else:
            print self.name + " skipped" 
            self.progress = 100.
            self.timeTotal = 0.
            self.isPaused = False
            self.isRunning = False
            self.isFinished = True
            self.finished.emit()
        
    def setLoops(self, value): 
        if value > self.loopCounter:            
            self.loops = value
        elif self.isRunning or self.isPaused:
            self.loops = self.loopCounter
        else:
            self.loops = value
#        if (not self.isFinished) and (self.loops):  
#            self.loops = value
        self.recalculate() 
        
    def pause(self):
        # using DirectConnection to invoke a method in another thread
        # note sure how safe it is but it works
        # SLOT should be seen in QT META OBJECT SPACE 
        # therefore, @QtCore.pyqtSlot() macro should be used on the method
        QtCore.QMetaObject.invokeMethod(self.taskWorker, "pause", QtCore.Qt.DirectConnection)
        self.isPaused = True
        self.isRunning = False
        logging.getLogger('').debug(self.taskName + " <" + self.name + "> paused")
    
    def update(self, i, v):    
        self.currentPoint = i
        self.progress = 100.*(sum(self.tppList[:i+1]) + self.time4loop*(self.loopCounter-1))/self.timeTotal
        self.updateProgress.emit(self.progress)
        self.updateData.emit([{
                               "name" : "Energy",
                               "addr" : "*****",
                               "pos"  : self.posList[i]
                              },                               
                              {
                               "name" : "i0",
                               "type" : "0d",
                               "value": 1.
                              },
                              {
                               "name" : "i1",
                               "type" : "0d",
                               "value": -v
                              },
                              {
                               "name" : "mu01",
                               "type" : "mu",
                               "value": v
                              },
                              {
                               "name" : "HPGe100pix",
                               "type" : "2d",
                               "value": np.random.randint(1024, size=(2048, 100))
                              } 
                             ]
                            )
        
    def finish(self):
        if self.loopCounter < self.loops:
            self.start()
        else:
            logging.getLogger('').info(self.taskName + " <" + self.name + "> (%d/%d) finished"%(self.loopCounter, self.loops) )        
            self.isPaused = False
            self.isRunning = False
            self.isFinished = True
            self.isEditable = True
            self.finished.emit()

