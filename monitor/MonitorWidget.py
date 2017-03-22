from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
#import numpy as np

class MonitorWidget(FigureCanvas):   
    def __init__(self): 
        self.fig = Figure()
        self.ax1 = self.fig.add_subplot(111)
        FigureCanvas.__init__(self, self.fig)
        self.ax1.set_xlabel("Position/Energy")        
        self.datax = []
        self.datay = []
        self.line, = self.ax1.plot(self.datax, self.datay, "ro-", lw = 2, label='data')
        self.fig.tight_layout()
        self.fig.canvas.draw()
        
    def updateData(self, data):
        if data:
            self.datax += list([data[0]])
            self.datay += list([data[1]])
            self.replot()
            
            
    def replot(self):        
        xmin, xmax = [min(self.datax) - 0.05*(max(self.datax) - min(self.datax)), max(self.datax) + 0.05*(max(self.datax) - min(self.datax))]
        ymin, ymax = [min(self.datay) - 0.05*(max(self.datay) - min(self.datay)), max(self.datay) + 0.05*(max(self.datay) - min(self.datay))]
        if xmin!= xmax or ymin!=ymax:
            self.ax1.axis([xmin, xmax, ymin, ymax])
        self.line.set_data(self.datax, self.datay) 
        self.ax1.legend(loc = "best").draw_frame(False)
        self.fig.canvas.draw()    
    
    def clearData(self):
        self.datax = []
        self.datay = []
       
