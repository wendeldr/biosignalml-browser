import sys
import re
import logging

from PyQt5 import QtCore, QtGui, QtWidgets

from ui.chart      import Ui_Chart
from ui.controller import Ui_Controller

from biosignalml import BSML
from biosignalml.data import DataSegment
import biosignalml.model
import biosignalml.units as uom

from nrange import NumericRange
from table import SortedTable


def wfdbAnnotation(e):
#=====================
  import wfdb
  mark = wfdb.annstr(int(e))
  ##  text = "Pacing on" if t < 100 else "Pacing off"   ########
  ##  chart.annotate(text, t, 0.0, textpos=(t, 1.05))
  if mark in "NLRBAaJSVrFejnE/fQ?":
    if mark == 'N': mark = u'\u2022'  # Unicode bullet
    return (mark, wfdb.anndesc(int(e)))
  return ('', '')

PREFIXES = {
  'bsml': 'http://www.biosignalml.org/ontologies/2011/04/biosignalml#',
  'dct':  'http://purl.org/dc/terms/',
  'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
  'pbank':	'http://www.biosignalml.org/ontologies/examples/physiobank#',
  }

def abbreviate_uri(uri):
#=======================
  v = str(uri)
  for pfx, ns in PREFIXES.items():
    if v.startswith(ns): return '%s:%s' % (pfx, v[len(ns):])
  return v

def expand_uri(uri):
#===================
  v = str(uri)
  for pfx, ns in PREFIXES.items():
    if v.startswith(pfx+':'): return ns + v[len(pfx)+1:]
  return v


def signal_uri(signal):
#======================
  prefix = str(signal.recording.uri)
  uri = str(signal.uri)
  if uri.startswith(prefix): return uri[len(prefix):]
  else:                      return uri


class SignalReadThread(QtCore.QThread):
#======================================

  append_points = QtCore.pyqtSignal(str, DataSegment)

  def __init__(self, sig, interval, plotter):
  #------------------------------------------
    QtCore.QThread.__init__(self)
    self._signal = sig
    self._id = signal_uri(sig)
    self._interval = interval
    self.append_points.connect(plotter.ui.chart.appendData)

  def run(self):
  #-------------
    self._exit = False
    self.append_points.emit(self._id, DataSegment(0, None))
    try:
      for d in self._signal.read(self._interval, maxpoints=20000):
        self.append_points.emit(self._id, d)
        if self._exit: break
    except Exception as msg:
      logging.error(msg)

  def stop(self):
  #--------------
    self._exit = True


class ChartForm(QtWidgets.QWidget):
#==================================

  def __init__(self, uri, start, duration, parent=None):
  #-----------------------------------------------------
    QtWidgets.QWidget.__init__(self, parent) # , QtCore.Qt.CustomizeWindowHint
#                                       | QtCore.Qt.WindowMinMaxButtonsHint
#                           #           | QtCore.Qt.WindowStaysOnTopHint
#                          )
    closekey = QtWidgets.QShortcut(QtGui.QKeySequence.Close, self, activated=self.close)
    self.ui = Ui_Chart()
    self.ui.setupUi(self)
    self.ui.chart.chartPosition.connect(self.on_chart_resize)
    self.ui.chart.updateTimeScroll.connect(self.position_timescroll)
    self.ui.timescroll.hide()
    self.setWindowTitle(uri)
    self.ui.chart.setId(uri)
    self.setTimeRange(start, duration)
    self._user_zoom_index = self.ui.timezoom.count()
    self.ui.chart.zoomChart.connect(self.zoom_chart)


  def setTimeRange(self, start, duration):
  #---------------------------------------
    self.ui.chart.setTimeRange(start, duration)
    self.ui.chart.setTimeScroll(self.ui.timescroll)

  def setSemanticTags(self, tag_dict):
  #-----------------------------------
    self.ui.chart.setSemanticTags(tag_dict)

  def setMarker(self, time):
  #-------------------------
    self.ui.chart.setMarker(time)

  def addSignalPlot(self, id, label, units, visible=True, data=None, ymin=None, ymax=None):
  #----------------------------------------------------------------------------------------
    self.ui.chart.addSignalPlot(id, label, units, visible=visible, data=data, ymin=ymin, ymax=ymax)

  def addEventPlot(self, id, label, mapping=lambda x: str(x), visible=True, data=None):
  #------------------------------------------------------------------------------------
    self.ui.chart.addEventPlot(id, label, mapping, visible=visible, data=data)

  def addAnnotation(self, id, start, end, text, tags, edit=False):
  #---------------------------------------------------------------
    self.ui.chart.addAnnotation(id, start, end, text, tags, edit)

  def deleteAnnotation(self, id):
  #------------------------------
    self.ui.chart.deleteAnnotation(id)

  def setPlotVisible(self, id, visible=True):
  #------------------------------------------
    self.ui.chart.setPlotVisible(id, visible)

  def orderPlots(self, ids):
  #-------------------------
    self.ui.chart.orderPlots(ids)

  def movePlot(self, from_id, to_id):
  #----------------------------------
    self.ui.chart.movePlot(from_id, to_id)

  def plotSelected(self, row):
  #---------------------------
    self.ui.chart.plotSelected(row)

  def resetAnnotations(self):
  #--------------------------
    self.ui.chart.resetAnnotations()

  def save_chart_as_png(self, filename):
  #-------------------------------------
    self.ui.chart.save_as_png(filename)

  def resizeEvent(self, e):
  #------------------------
    self.ui.layoutWidget.setGeometry(QtCore.QRect(10, 25, self.width()-20, self.height() - 50))

  def on_timescroll_valueChanged(self, position):
  #----------------------------------------------
    self.ui.chart.moveTimeScroll(self.ui.timescroll)

  def position_timescroll(self, visible):
  #--------------------------------------
    self.ui.chart.setTimeScroll(self.ui.timescroll)
    self.ui.timescroll.setVisible(visible)

  def on_timezoom_currentIndexChanged(self, text):
  #-----------------------------------------------
    if isinstance(text, basestring) and text != "":
      scale = float(str(text).split()[0])
      self.ui.chart.setTimeZoom(scale)
      self.position_timescroll(scale > 1.0)

  def zoom_chart(self, scale):
  #---------------------------
    if self.ui.timezoom.count() > self._user_zoom_index:
      self.ui.timezoom.setItemText(self._user_zoom_index, "%.2f x" % scale)
    else:
      self.ui.timezoom.insertItem(self._user_zoom_index, "%.2f x" % scale)
    self.ui.timezoom.setCurrentIndex(-1)
    self.ui.timezoom.setCurrentIndex(self._user_zoom_index)
    # Above will trigger on_timezoom_currentIndexChanged()

  def position_timescroll(self, visible):
  #--------------------------------------
    self.ui.chart.setTimeScroll(self.ui.timescroll)
    self.ui.timescroll.setVisible(visible)

  def on_frame_frameResize(self, geometry):
  #----------------------------------------
    geometry.adjust(3, 3, -3, -3)
    self.ui.chart.setGeometry(geometry)
    #QtCore.QRect(offset-4, self.height()-40, width+8, 30))

  def on_chart_resize(self, offset, width, bottom):
  #------------------------------------------------
    h = self.ui.timescroll.height()
    self.ui.timescroll.setGeometry(QtCore.QRect(offset-10, bottom+27, width+40, h))

  def on_chart_customContextMenuRequested(self, pos):
  #--------------------------------------------------
    self.ui.chart.contextMenu(pos)



class SignalInfo(QtCore.QAbstractTableModel):
#============================================

  rowVisible = QtCore.pyqtSignal(str, bool)   # id, state
  rowMoved = QtCore.pyqtSignal(str, str)      # from_id, to_id

  HEADER    = [ '', 'Label', 'Uri' ]
  ID_COLUMN = 2                               # Uri is ID

  def __init__(self, recording, *args, **kwds):
  #--------------------------------------------
    QtCore.QAbstractTableModel.__init__(self, *args, **kwds)
    self._rows = [ [True, s.label, signal_uri(s)]
                     for n, s in enumerate(recording.signals()) ]

  def rowCount(self, parent=None):
  #-------------------------------
    return len(self._rows)

  def columnCount(self, parent=None):
  #----------------------------------
    return len(self.HEADER)

  def headerData(self, section, orientation, role):
  #------------------------------------------------
    if orientation == QtCore.Qt.Horizontal:
      if role == QtCore.Qt.DisplayRole:
        return self.HEADER[section]
      elif role == QtCore.Qt.TextAlignmentRole:
        return QtCore.Qt.AlignLeft
      elif role == QtCore.Qt.FontRole:
        font = QtGui.QFont(QtWidgets.QApplication.font())
        font.setBold(True)
        return font

  def data(self, index, role):
  #---------------------------
    if   role == QtCore.Qt.DisplayRole:
      if index.column() != 0:
        return str(self._rows[index.row()][index.column()])
      else:
        return QtCore.QVariant()
    elif role == QtCore.Qt.CheckStateRole:
      if index.column() == 0:
        return QtCore.Qt.Checked if self._rows[index.row()][0] else QtCore.Qt.Unchecked

  def setData(self, index, value, role):
  #-------------------------------------
    if role == QtCore.Qt.CheckStateRole and index.column() == 0:
      self._rows[index.row()][0] = (value == QtCore.Qt.Checked)
      self.rowVisible.emit(self._rows[index.row()][self.ID_COLUMN], (value == QtCore.Qt.Checked))
      self.dataChanged.emit(index, index)
      return True
    return False

  def moveRow(self, sourceindex, sourcerow, destindex, destrow):
  #-------------------------------------------------------------
    data = self._rows[sourcerow]
    from_id = data[self.ID_COLUMN]
    if sourcerow > destrow:        # Moving up
      to_id = self._rows[destrow][self.ID_COLUMN]
      self._rows[destrow+1:sourcerow+1] = self._rows[destrow:sourcerow]
      self._rows[destrow] = data
    elif (sourcerow+1) < destrow:  # Moving down
      to_id = self._rows[destrow-1][self.ID_COLUMN]
      self._rows[sourcerow:destrow-1] = self._rows[sourcerow+1:destrow]
      self._rows[destrow-1] = data
    self.rowMoved.emit(from_id, to_id)

  def flags(self, index):
  #-----------------------
    if index.column() == 0:
      return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsSelectable
    else:
      return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

  def setVisibility(self, visible):
  #--------------------------------
    for r in xrange(len(self._rows)):
      self.setData(self.createIndex(r, 0),
                   QtCore.Qt.Checked if visible else QtCore.Qt.Unchecked,
                   QtCore.Qt.CheckStateRole)


class AnnotationTable(object):
#=============================

  @staticmethod
  def header():
  #------------
    return ['', 'Start', 'End', 'Duration',  'Type', 'Annotation', 'Tags']

  @staticmethod
  def row(uri, times, type, text, tagtext=''):
  #---=---------------------------------------
    return [str(uri)] + times + [ type, text, tagtext ]


class Controller(QtWidgets.QWidget):
#===================================

  def __init__(self, store, rec_uri, recording=None, parent=None):
  #---------------------------------------------------------------
    QtWidgets.QWidget.__init__(self, parent) # , QtCore.Qt.CustomizeWindowHint
#                                       | QtCore.Qt.WindowMinMaxButtonsHint
#                           #           | QtCore.Qt.WindowStaysOnTopHint
#                          )

    closekey = QtWidgets.QShortcut(QtGui.QKeySequence.Close, self, activated=self.close)
    self.controller = Ui_Controller()
    self.controller.setupUi(self)
    self._graphstore = store
    self._readers = [ ]

    start = 0.0
    end = None
    rec_uri = str(rec_uri)
    mediatag = rec_uri.rfind('#t=')
    if mediatag >= 0:
      tag = rec_uri[mediatag+3:]
      rec_uri = rec_uri[:mediatag]
      try:
        times = re.match('(.*?)(,(.*))?$', tag).groups()
        start = float(times[0])
        end = float(times[2])
      except ValueError:
        pass

    if recording is None:
      self._recording = store.get_recording(rec_uri)
    else:
      self._recording = recording
    if self._recording is None:
      raise IOError("Unknown recording: %s" % rec_uri)
    self.uri = str(self._recording.uri)
    self.setWindowTitle(self.uri)
    self._make_uri = self._recording.uri.make_uri    # Method for minting new URIs

    if end is None:
      duration = self._recording.duration
      if duration is None or duration <= 0.0:
        self._recording.duration = duration = 60.0    ######
    elif start <= end:
      duration = end - start
    else:
      duration = start - end
      start = end

    self._start = start
    self._duration = duration
    self.controller.rec_posn = QtWidgets.QLabel(self)
    self.controller.rec_posn.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
    self.controller.rec_posn.resize(self.controller.rec_start.size())
    self.controller.splitter.splitterMoved.connect(self._splitter_moved)

    self._timerange = NumericRange(0.0, duration)

    annotator = wfdbAnnotation   ##################

    self.semantic_tags = store.get_semantic_tags()

    self._annotations = [ ]     # tuple(uri, start, end, text, tags, editable, resource)
    for a in store.get_annotations(rec_uri, self._recording.graph):
      if a.time is None:
        annstart = None
        annend   = None
      else:
        annstart = a.time.start
        annend   = None if a.time.duration in [None, 0.0] else a.time.end
      self._annotations.append( (str(a.uri), annstart, annend,
                                 a.comment if a.comment is not None else '',
                                 a.tags, True, a) )
##      print (str(a.uri), annstart, annend, str(a.comment), a.tags)
    for e in [store.get_event(evt, self._recording.graph)
                for evt in store.get_event_uris(rec_uri, timetype=BSML.Interval, graph_uri=self._recording.graph)]:
      self._annotations.append( (str(e.uri), e.time.start, e.time.end, abbreviate_uri(e.eventtype), None, False, e) )

    self._annotation_table = SortedTable(self.controller.annotations, AnnotationTable.header(),
                                         [ AnnotationTable.row(a[0], self._make_ann_times(a[1], a[2]),
                                                              'Annotation' if a[5] else 'Event',
                                                              a[3], self._tag_labels(a[4]))
                                             for a in self._annotations ],
                                         parent=self)
    self._events = { }
    self._event_type = None
    self._event_rows = None
    self.controller.events.addItem('None')
    self.controller.events.insertItems(1, ['%s (%s)' % (abbreviate_uri(etype), count)
      for etype, count in store.event_types(rec_uri, counts=True, graph_uri=self._recording.graph)])
      # if no duration ...
    self.controller.events.addItem('All')
    self._event_type = 'None'

    self.model = SignalInfo(self._recording)
    self.controller.signals.setModel(self.model)
    self.controller.signals.setColumnWidth(0, 25)

    self.viewer = ChartForm(self.uri, self._start, self._duration)
    self.model.rowVisible.connect(self.viewer.setPlotVisible)
    self.model.rowMoved.connect(self.viewer.movePlot)
    self.controller.signals.rowSelected.connect(self.viewer.plotSelected)
    self.viewer.ui.chart.annotationAdded.connect(self.annotationAdded)
    self.viewer.ui.chart.annotationModified.connect(self.annotationModified)
    self.viewer.ui.chart.annotationDeleted.connect(self.annotationDeleted)
    self.viewer.ui.chart.exportRecording.connect(self.exportRecording)

    self.viewer.setSemanticTags(self.semantic_tags)

    interval = self._recording.interval(self._start, self._duration)
    self._setup_slider()
    for s in self._recording.signals():
      uri = signal_uri(s)
      if str(s.units) == str(uom.UNITS.AnnotationData.uri):
        self.viewer.addEventPlot(uri, s.label, annotator)
      else:
        try: units = uom.RESOURCES[str(s.units)].label
        except: units = str(s.units)
        self.viewer.addSignalPlot(uri, s.label, units) ## , ymin=s.minValue, ymax=s.maxValue)
    self._plot_signals(interval)
    for a in self._annotations:  # tuple(uri, start, end, text, tags, resource)
      if a[1] is not None: self.viewer.addAnnotation(*a[:6])
    # self.setFocusPolicy(QtCore.Qt.StrongFocus) # Needed to handle key events
    self.viewer.show()

  def __del__(self):
  #-----------------
    self._stop_readers()

  def _plot_signals(self, interval):
  #---------------------------------
    self._stop_readers()
    self.viewer.resetAnnotations()
    for s in self._recording.signals():
      self._readers.append(SignalReadThread(s, interval, self.viewer))
      self._readers[-1].start()

  def _stop_readers(self):
  #-----------------------
    for t in self._readers: t.stop()
    while True:
      stopped = True
      for t in self._readers:
        stopped = stopped and t.wait(10)
      if stopped: break
    self._readers = [ ]

  def _make_ann_times(self, start, end):
  #-------------------------------------
    if start is None:
      return ['', '', '']
    else:
      nstart = self._timerange.map(start)  # Normalise for display
      if end is not None:
        nend = self._timerange.map(end)
        return [ nstart, nend, nend - nstart ]
      else:
        return [ nstart, '', '' ]

  def _tag_labels(self, tags):
  #---------------------------
    if tags is None:
      return ''
    else:
      return ', '.join(sorted([self.semantic_tags.get(str(t), str(t)) for t in tags]))

  def _adjust_layout(self):
  #------------------------
    self.controller.annotations.resizeCells()
    self._show_slider_time(self._start)

  def resizeEvent(self, event):
  #----------------------------
    self._adjust_layout()

  def _splitter_moved(self, pos, index):
  #-------------------------------------
    self._adjust_layout()

  def showEvent(self, event):
  #--------------------------
#    if self.controller.rec_posn.pos().y() == 0:  # After laying out controller
    self._adjust_layout()
    QtWidgets.QWidget.showEvent(self, event)

  def _set_slider_time(self, label, time):
  #---------------------------------------
    ## Show as HH:MM:SS
    label.setText(str(self._timerange.map(time, -1)))

  def _show_slider_time(self, time):
  #---------------------------------
    self._set_slider_time(self.controller.rec_posn, time)
    sb = self.controller.segment
    self.controller.rec_posn.move(  ## 50 = approx width of scroll end arrows
      20 + sb.pos().x() + (sb.width()-50)*time/self._recording.duration,
      self.controller.rec_start.pos().y() + 6)

  def _set_slider_value(self, time):
  #---------------------------------
    sb = self.controller.segment
    width = sb.maximum() + sb.pageStep() - sb.minimum()
    sb.setValue(width*time/self._recording.duration)

  def _setup_slider(self):
  #-----------------------
    self._sliding = True            ## So we don't move_viewer() when sliderMoved()
    self._move_timer = None         ## is triggered by setting the slider's value
    duration = self._recording.duration
    if duration == 0: return
    sb = self.controller.segment
    sb.setMinimum(0)
    scrollwidth = 10000
    sb.setPageStep(scrollwidth*self._duration/duration)
    sb.setMaximum(scrollwidth - sb.pageStep())
    sb.setValue(scrollwidth*self._start/duration)
    self._set_slider_time(self.controller.rec_start, 0.0)
    self._set_slider_time(self.controller.rec_end, duration)

  def _stop_move_timer(self):
  #--------------------------
    if self._move_timer is not None:
      self.killTimer(self._move_timer)
      self._move_timer = None

  def _start_move_timer(self):
  #---------------------------
    if self._move_timer is not None:
      self.killTimer(self._move_timer)
    self._move_timer = self.startTimer(100)  # 100ms

  def timerEvent(self, event):
  #---------------------------
    if self._move_timer is not None:
      self._stop_move_timer()
      self._move_viewer(self._newstart)

  def _slider_moved(self):
  #-----------------------
    sb = self.controller.segment
    duration = self._recording.duration
    width = sb.maximum() + sb.pageStep() - sb.minimum()
    self._newstart = sb.value()*duration/float(width)
    self._show_slider_time(self._newstart)
    if self.controller.segment.isSliderDown():
      self._start_move_timer()
      self._sliding = True
    elif self._sliding:
      if self._move_timer is not None:
        self._stop_move_timer()
        self._move_viewer(self._newstart)
      self._sliding = False
    else:
      self._move_viewer(self._newstart)

  def _move_viewer(self, start):
  #-----------------------------
    if start != self._start:
      self._plot_signals(self._recording.interval(start, self._duration))
      self.viewer.setTimeRange(start, self._duration)
      self._start = start
      for a in self._annotations:  # tuple(uri, start, end, text, tags, resource)
        if a[1] is not None: self.viewer.addAnnotation(*a[:6])

  def on_segment_valueChanged(self, position):
  #-------------------------------------------
    self._slider_moved()
    # Sluggish if large data segments with tracking...
  # Tracking is on, show time at slider posiotion
  # But also catch slider released and use this to refresh chart data...

  def on_segment_sliderReleased(self):
  #-----------------------------------
    self._slider_moved()

  def on_allsignals_toggled(self, state):
  #--------------------------------------
    self.model.setVisibility(state)

  def _find_annotation(self, id):
  #------------------------------
    for ann in self._annotations:
      if id == ann[0]: return ann

  def _delete_annotation(self, id):
  #--------------------------------
    for n, ann in enumerate(self._annotations):
      if id == ann[0]:
        del self._annotations[n]
        return

  def on_annotations_doubleClicked(self, index):
  #---------------------------------------------
    source = index.model().mapToSource(index)
    id = source.model().createIndex(source.row(), 0).data()
    ann = self._find_annotation(id)
    time = None
    duration = None
    if ann and ann[1] is not None:
      time = ann[1]
      if ann[2] is not None:
        duration = ann[2] - time
    else:
      evt = self._events.get(id, None)
      if evt is not None:
        time = evt[0]
        duration = evt[1]
    if time is not None:
      if duration is not None:
        start = max(0.0, time - duration/2.0)
        end = min(time + duration + duration/2.0, self._recording.duration)
        self._duration = end - start
      else:
        start = max(0.0, time - self._duration/4.0)
      self._move_viewer(start)
      self._set_slider_value(start)
      self._show_slider_time(start)
      self.viewer.setMarker(time)

  def on_events_currentIndexChanged(self, index):
  #----------------------------------------------
    if (self._event_type is None      # Setting up
     or not isinstance(index, basestring)): return
    if self._event_rows is not None:
      self._annotation_table.removeRows(self._event_rows)
    if index == 'None':
      self._event_rows = None
      return
    if index == 'All': etype = None
    else: etype = expand_uri(str(index).rsplit(' (', 1)[0])
    events = [ self._graphstore.get_event(evt, self._recording.graph)
                 for evt in self._graphstore.events(self.uri, eventtype=etype,
                                                    timetype=BSML.Instant, graph_uri=self._recording.graph) ]
    self._events = { str(event.uri): (event.time.start, event.time.duration) for event in events }
    self._event_rows = self._annotation_table.appendRows([ AnnotationTable.row(event.uri,
                                                            [self._timerange.map(event.time.start),
                                                             self._timerange.map(event.time.end),
                                                             event.time.duration], 'Event',
                                                            abbreviate_uri(event.eventtype))
                                                         for event in events ])
    self._adjust_layout()

  def annotationAdded(self, start, end, text, tags, predecessor=None):
  #-------------------------------------------------------------------
    if text or tags:
      segment = biosignalml.model.Segment(self._make_uri(),
                                          self._recording,
                                          self._recording.interval(start, end=end))
      self._graphstore.extend_recording_graph(self._recording, segment)
      self._add_annotation(segment, text, tags, predecessor)

  def _add_annotation(self, about, text, tags, predecessor=None):
  #--------------------------------------------------------------
    annotation = biosignalml.model.Annotation(self._make_uri(),
                                              about=about,
                                              comment=text, tags=tags,
                                              precededBy=predecessor)
    self._graphstore.extend_recording_graph(self._recording, annotation)
    if annotation.time is not None:
      (start, end) = (annotation.time.start, annotation.time.end)
    else:
      (start, end) = (None, None)
    self._annotation_table.appendRows([ AnnotationTable.row(annotation.uri,
                                                            self._make_ann_times(start, end),
                                                            'Annotation', text,
                                                            self._tag_labels(tags)) ])
    self._annotations.append((str(annotation.uri), start, end, text, tags, True, annotation))
    self.viewer.addAnnotation(annotation.uri, start, end, text, tags, True)



  def _remove_annotation(self, id):
  #--------------------------------
    self._annotation_table.deleteRow(id)
    self._delete_annotation(id)
    self.viewer.deleteAnnotation(id)

  def annotationModified(self, id, text, tags):
  #--------------------------------------------
    ann = self._find_annotation(id)
    if ann is not None:
      self._remove_annotation(id)
      if text or tags:
        self._add_annotation(ann[6].about, text, tags, predecessor=id)

  def annotationDeleted(self, id):
  #-------------------------------
    self._remove_annotation(id)
    self._graphstore.remove_recording_resource(self._recording, id)


  def exportRecording(self, start, end):
  #-------------------------------------
    print('export', start, end)


  #def keyPressEvent(self, event):   ## Also need to do so in chart...
  #------------------------------    ## And send us hide/show messages or keys
  #  pass


def show_chart(store, recording, start=0.0, end=None):
#=====================================================
  try:
    ctlr = Controller(store, "%s#t=%g,%s" % (recording.uri, start, end if end is not None else ''))
  except IOError as msg:
    print(str(msg))
    return
  ctlr.viewer.raise_()
  ctlr.viewer.activateWindow()
  return ctlr


def show_recording(uri, start=0.0, end=None):
#============================================
  store = biosignalml.client.Repository(uri)
  try:
    ctlr = Controller(store, "%s#t=%g,%s" % (uri, start, end if end is not None else ''))
  except IOError as msg:
    sys.exit(str(msg))
  ctlr.viewer.raise_()
  ctlr.viewer.activateWindow()
  return ctlr


if __name__ == "__main__":
#=========================

  import biosignalml.client

  logging.basicConfig(format='%(asctime)s %(levelname)8s %(threadName)s: %(message)s')
  logging.getLogger().setLevel('DEBUG')

  ## Replace following with Python arg parser...
  if len(sys.argv) <= 1:
    print("Usage: %s recording_uri [start] [duration]" % sys.argv[0])
    sys.exit(1)

  app = QtWidgets.QApplication(sys.argv)

  rec_uri = sys.argv[1]
  if len(sys.argv) >= 3:
    try:
      start = float(sys.argv[2])
    except:
      print("Invalid start time")
      sys.exit(1)
  else:
    start = 0.0
  if len(sys.argv) >= 4:
    try:
      end = start + float(sys.argv[3])
    except:
      print("Invalid duration")
      sys.exit(1)
  else:
    end = None

  viewer = show_recording(rec_uri, start, end)
  viewer.show()

  sys.exit(app.exec_())
