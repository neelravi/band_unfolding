#! /usr/bin/env python
# Copyright (C) 2014 Paulo V. C. Medeiros (paume@ifm.liu.se)
# This file is part of BandUP: Band Unfolding code for Plane-wave based calculations.
#
# BandUP is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
#  BandUP is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with BandUP.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import division
import sys
import os
import matplotlib.colors
import matplotlib.pyplot as plt
from fractions import Fraction
try:
    from PyQt4 import QtGui, QtCore, uic
except ImportError:
    import Tkinter
    import tkMessageBox
    root = Tkinter.Tk()
    root.withdraw()
    tkMessageBox.showerror("BandUP plot GUI", 
                           "Sorry, but you don't seem to have PyQt4 available in your python install. \n" + 
                           "Please use the plotting tool through the command line.")
    sys.exit(0)
import json


# Trick to avoid errors with PlaceholderText for Qt4.X, X<7.
if('setPlaceholderText' not in dir(QtGui.QLineEdit)):
    def redefined_setPlaceholderText(lineEdit, text):
        lineEdit._placeholderText = QtCore.QString(text)
        lineEdit.setText(text)
    def redefined_PlaceholderText(lineEdit):
        return lineEdit._placeholderText

    QtGui.QLineEdit.setPlaceholderText = redefined_setPlaceholderText
    QtGui.QLineEdit.PlaceholderText = redefined_PlaceholderText


def find(name, path):
    # From http://stackoverflow.com/questions/1724693/find-a-file-in-python
    for root, dirs, files in os.walk(path):
        if name in files:
            return os.path.join(root, name)

def allowed_fig_formats():
    temp_fig = plt.figure()
    allowed_filetypes = [f.lower() for f in temp_fig.canvas.get_supported_filetypes().keys()]
    plt.close(temp_fig)
    return allowed_filetypes

def set_default_fig_format(allowed_filetypes, default_fig_format='tiff'):
    if default_fig_format not in allowed_filetypes:
        default_fig_format = allowed_filetypes[0]
    return default_fig_format

def center_window(window):
    # From http://zetcode.com/gui/pyqt4
    qr = window.frameGeometry()
    cp = QtGui.QDesktopWidget().availableGeometry().center()
    qr.moveCenter(cp)
    window.move(qr.topLeft())

class MyOutputWindow(QtGui.QWidget):
    def __init__(self, parent=None, dimensions=(1000, 750)):
        super(MyOutputWindow, self).__init__()
        self.setParent(parent)
        self.initUI(dimensions)

    def initUI(self, dimensions):
        self.resize(dimensions[0], dimensions[1])
        center_window(self)
        # Menu bar
        menubar_end_y = 31
        self.menubar = QtGui.QMenuBar(self)
        self.menubar.resize(dimensions[0], menubar_end_y)
        fileMenu = self.menubar.addMenu('File')
        # QTextEdit
        self.edit = QtGui.QTextEdit(self)
        self.edit.setGeometry(QtCore.QRect(0, menubar_end_y, dimensions[0], dimensions[1]))
        self.edit.setReadOnly(True)

        self.show()  


class MyQProcess(QtCore.QProcess):    
    ''' Adapted from 
        http://codeprogress.com/python/libraries/pyqt/showPyQTExample.php?index=408&key=QTextEditRedStdOutput 
        and
        http://stackoverflow.com/questions/22069321/realtime-output-from-a-subprogram-to-stdout-of-a-pyqt-widget'''
    def __init__(self, parent=None, output_window_title=''):    
        super(MyQProcess, self).__init__()
        self.setParent(parent)
        # This is to give QProcess real-time access to the plotting tool's output
        # See http://stackoverflow.com/questions/107705/python-output-buffering
        os.environ['PYTHONUNBUFFERED'] = 'True'
        self.initUI(output_window_title)

    def initUI(self, window_title=''):
        self.w = MyOutputWindow()
        self.w.setWindowTitle(window_title)
        self.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.readyRead.connect(lambda: self.dataReady())

    def dataReady(self):
        cursor = self.w.edit.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(str(self.readAll()))
        self.w.edit.ensureCursorVisible()


class BandupPlotToolWindow(QtGui.QMainWindow):
    def __init__(self):
        super(BandupPlotToolWindow, self).__init__()
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        self.folder_gui_script_is_located = os.path.abspath(os.path.dirname(os.path.realpath(sys.argv[0])))
        try:
            if(os.path.isdir(sys.argv[1])):
                os.chdir(sys.argv[1])
        except IndexError:
            pass
        self.folder_where_gui_has_been_called = os.getcwd()

        plot_script_fname = 'plot_unfolded_EBS_BandUP.py'
        self.plot_script = os.path.join(os.environ['BANDUPPLOTPATH'], plot_script_fname)
        if(not os.path.isfile(self.plot_script)):
            reply = QtGui.QMessageBox.critical(self, "Error: BandUP's Plotting script not found", 
                                               'The file \n %s file could not be found. \n'\
                                               'Please set the environment variable "BANDUPPLOTPATH" '\
                                               'to the directory where the file %s is located.'\
                                               % (self.plot_script, plot_script_fname), QtGui.QMessageBox.Close)
            sys.exit(0)

        self.last_folder = QtCore.QString(self.folder_where_gui_has_been_called)
        self.default_aspect_ratio = QtCore.QString('3/4')
        self.vmin = None
        self.vmax = None
        self.aspect_ratio = None

        self.initUI()

    def try_to_get_plot_boundaries_from_energy_file(self):
        self.min_E = None
        self.max_E = None
        self.min_k = None
        self.max_k = None
        try:
            with open(self.energy_file_path) as energy_info_file:
                energy_info_file_lines = energy_info_file.readlines()
                try: 
                    self.min_E = float(energy_info_file_lines[1].split()[0])
                except(ValueError, IndexError):
                    pass
                try: 
                    self.max_E = float(energy_info_file_lines[2].split()[0])
                except(ValueError, IndexError):
                    pass
                try: 
                    self.min_k = float(energy_info_file_lines[1].split()[1])
                except(ValueError, IndexError):
                    pass
                try: 
                    self.max_k = float(energy_info_file_lines[2].split()[1])
                except(ValueError, IndexError):
                    pass
                try:
                   self.dE_spinBox.setValue(float(energy_info_file_lines[3].split()[0]))
                except(ValueError, IndexError):
                    pass
        except (IOError, TypeError):
            pass

        if(self.min_k is not None and self.max_k is not None and self.min_k > self.max_k):
            self.min_k, self.max_k = self.max_k, self.min_k
        if(self.min_E is not None and self.max_E is not None and self.min_E > self.max_E):
            self.min_E, self.max_E = self.max_E, self.min_E
        if(self.min_E): 
            self.min_E_lineEdit.setText(str(self.min_E)) 
        if(self.max_E): 
            self.max_E_lineEdit.setText(str(self.max_E))
        if(self.min_k):
            self.min_k_lineEdit.setText(str(self.min_k)) 
        if(self.max_k):
            self.max_k_lineEdit.setText(str(self.max_k)) 


    def initUI(self):
        # Loading the base UI I've created using QT Designer
        ui_file = os.path.join(self.folder_gui_script_is_located, 'BandUP_plot_GUI.ui') 
        uic.loadUi(ui_file, self)

        self.aspect_ratio_lineEdit.setPlaceholderText(self.default_aspect_ratio)

        def set_defualt_file_path(file_lineEdit, trial_file_path):
            file_lineEdit.setText('')
            trial_file_path = os.path.abspath(str(trial_file_path))
            file_exists = os.path.isfile(trial_file_path)
            if(file_exists):
                file_lineEdit.default_file_path = QtCore.QString(trial_file_path)
                file_lineEdit.default_text = QtCore.QString('Default: %s' % trial_file_path)
            else:
                file_lineEdit.default_file_path = None
                if(file_lineEdit == self.select_energy_file_lineEdit):
                    file_lineEdit.default_text = QtCore.QString('Optional')
                else:
                    file_lineEdit.default_text = QtCore.QString('Select...')

            file_lineEdit.previous_valid_file_path = file_lineEdit.default_file_path
            if(len(str(file_lineEdit.default_text)) < 30):
                file_lineEdit.setPlaceholderText(file_lineEdit.default_text)
            else:
                file_lineEdit.setPlaceholderText('...' + str(file_lineEdit.default_text)[-30:])
        
        # Defaults for the input prim. cell file
        set_defualt_file_path(self.select_prim_cell_file_lineEdit, 'prim_cell_lattice.in')
        self.prim_cell_file_path = self.select_prim_cell_file_lineEdit.default_file_path
        # Defaults for the input pc-kpts file
        set_defualt_file_path(self.select_pckpts_file_lineEdit, 'KPOINTS_prim_cell.in')
        self.pckpts_file_path = self.select_pckpts_file_lineEdit.default_file_path
        # Defaults for the input energy config. file
        set_defualt_file_path(self.select_energy_file_lineEdit, 'energy_info.in')
        self.energy_file_path = self.select_energy_file_lineEdit.default_file_path
        self.try_to_get_plot_boundaries_from_energy_file()
        # Defaults for the input EBS file (BandUP's output)
        set_defualt_file_path(self.select_EBS_file_lineEdit, 'unfolded_EBS_symmetry-averaged.dat')
        self.EBS_file_path = self.select_EBS_file_lineEdit.default_file_path
        # Defaults for the out fig. file
        self.default_out_figure_file_path = None
        self.out_figure_file_path = self.default_out_figure_file_path
        self.select_out_figure_file_lineEdit.default_text = "Auto, derived from input file"
        self.select_out_figure_file_lineEdit.setPlaceholderText(self.select_out_figure_file_lineEdit.default_text)
        self.update_lineEdit_completer()

        # Connecting lineEdit objects
        self.select_prim_cell_file_lineEdit.editingFinished.connect(lambda: self.on_editing_input_file_lineEdits(self.select_prim_cell_file_lineEdit))
        self.select_pckpts_file_lineEdit.editingFinished.connect(lambda: self.on_editing_input_file_lineEdits(self.select_pckpts_file_lineEdit))
        self.select_energy_file_lineEdit.editingFinished.connect(lambda: self.on_editing_input_file_lineEdits(self.select_energy_file_lineEdit))
        self.select_EBS_file_lineEdit.editingFinished.connect(lambda: self.on_editing_input_file_lineEdits(self.select_EBS_file_lineEdit))
        self.select_out_figure_file_lineEdit.editingFinished.connect(self.on_editing_output_file_lineEdit)
        self.vmin_lineEdit.editingFinished.connect(self.on_vmin_change)
        self.vmax_lineEdit.editingFinished.connect(self.on_vmax_change)
        self.aspect_ratio_lineEdit.editingFinished.connect(self.on_aspect_ratio_change)
        self.min_E_lineEdit.editingFinished.connect(self.on_min_E_change)
        self.max_E_lineEdit.editingFinished.connect(self.on_max_E_change)
        self.min_k_lineEdit.editingFinished.connect(self.on_min_k_change)
        self.max_k_lineEdit.editingFinished.connect(self.on_max_k_change)
        # Connecting the file choice buttons
        self.select_prim_cell_file_Button.clicked.connect(lambda: self.selectFile(self.select_prim_cell_file_Button, self.select_prim_cell_file_lineEdit))
        self.select_pckpts_file_Button.clicked.connect(lambda: self.selectFile(self.select_pckpts_file_Button, self.select_pckpts_file_lineEdit))
        self.select_energy_file_Button.clicked.connect(lambda: self.selectFile(self.select_energy_file_Button, self.select_energy_file_lineEdit))
        self.select_EBS_file_Button.clicked.connect(lambda: self.selectFile(self.select_EBS_file_Button, self.select_EBS_file_lineEdit))
        self.select_out_figure_file_Button.clicked.connect(lambda: self.selectFile(self.select_out_figure_file_Button, self.select_out_figure_file_lineEdit))
        # Managing checkBox objects
        self.show_colorbar_checkBox.stateChanged.connect(self.on_show_colorbar_checkBox_stateChanged)
        self.show_colorbar_full_label_checkBox.setEnabled(self.show_colorbar_label_checkBox.isEnabled() and 
                                                          self.show_colorbar_label_checkBox.isChecked())
        self.save_figure_checkBox.stateChanged.connect(self.on_save_figure_checkBox_stateChanged)
        self.show_figure_checkBox.stateChanged.connect(self.on_show_figure_checkBox_stateChanged)
        # Managing comboBox objects        
        self.colormap_comboBox.insertItems(1, self.get_available_cmaps())
        mpl_colors = sorted(matplotlib.colors.cnames.keys())
        self.e_fermi_color_comboBox.insertItems(1, mpl_colors)
        self.high_symm_lines_color_comboBox.insertItems(1, mpl_colors)
        # Connecting the 'plot' button
        self.plot_pushButton.clicked.connect(self.onRun)
        # Scheduling the window to be shown at the center of the screen 
        center_window(self)
        self.show()


    def get_available_cmaps(self):
        colormap_names = []
        try:
            cmapnames = plt.cm._cmapnames
        except AttributeError:
            cmapnames = plt.cm.dated
        for m in cmapnames:
            colormap_names.append(m)
            if(m + '_r' in dir(plt.cm)):
                colormap_names.append(m + '_r')
        colormaps = dict([[cmap_name, plt.get_cmap(cmap_name)] for cmap_name in colormap_names])
        # Custom colormaps
        try:
            custom_cm_folder = os.path.join(os.environ['BANDUPPLOTPATH'], 'custom_colormaps')
            os_listdir_full_custom_cm_folder = [os.path.abspath(os.path.join(custom_cm_folder, cmap_file)) for cmap_file in os.listdir(custom_cm_folder)]
            custom_cmap_files = [cmap_file for cmap_file in os_listdir_full_custom_cm_folder if cmap_file.endswith('.cmap')]
            custom_cmaps = []
            for cmap_file in custom_cmap_files:
                cmap_name = os.path.splitext(os.path.basename(cmap_file))[0]
                color_dict = json.load(open(cmap_file))
                colormap_names.append(cmap_name)
                colormaps[cmap_name] = plt.cm.colors.LinearSegmentedColormap(cmap_name, color_dict, 2048)
        except:
            pass

        return sorted(colormap_names)


    def update_lineEdit_completer(self):
        self.files_in_current_folder = [QtCore.QString(item) for item in 
                                        os.listdir(str(self.last_folder)) if 
                                        os.path.isfile(os.path.join(str(self.last_folder), item))]
        self.file_lineEdit_completer = QtGui.QCompleter(self.files_in_current_folder)
        self.file_lineEdit_completer.setCompletionMode(QtGui.QCompleter.InlineCompletion)

        self.select_prim_cell_file_lineEdit.setCompleter(self.file_lineEdit_completer)
        self.select_pckpts_file_lineEdit.setCompleter(self.file_lineEdit_completer)
        self.select_energy_file_lineEdit.setCompleter(self.file_lineEdit_completer)
        self.select_EBS_file_lineEdit.setCompleter(self.file_lineEdit_completer)


    def on_show_colorbar_checkBox_stateChanged(self): 
        self.show_colorbar_full_label_checkBox.setEnabled(self.show_colorbar_label_checkBox.isEnabled() and 
                                                          self.show_colorbar_label_checkBox.isChecked())

    def on_save_figure_checkBox_stateChanged(self):
        if((not self.save_figure_checkBox.isChecked()) and
           (not self.show_figure_checkBox.isChecked())):
            self.show_figure_checkBox.setCheckState(QtCore.Qt.Checked)
    def on_show_figure_checkBox_stateChanged(self):
        if((not self.show_figure_checkBox.isChecked()) and
           (not self.save_figure_checkBox.isChecked())):
            self.save_figure_checkBox.setCheckState(QtCore.Qt.Checked)


    def on_editing_input_file_lineEdits(self, lineEdit):
        os.chdir(str(self.last_folder)) # This is to make the open/save file dialog screens remember the last folder
        entered_file_path = os.path.abspath(str(lineEdit.text()).strip())
        if(entered_file_path.startswith('file:')):
            entered_file_path = entered_file_path[5:]

        valid_file_entered = os.path.isfile(entered_file_path)
        if(valid_file_entered):
            file_path = QtCore.QString(entered_file_path)
            lineEdit.previous_valid_file_path = file_path
            if(file_path != lineEdit.default_file_path):
                lineEdit.setText(file_path)
            else:
                lineEdit.setText('')
        else:
            if(str(lineEdit.text()).strip() == ''): # i.e., if the user resets the lineEdit
                lineEdit.previous_valid_file_path = lineEdit.default_file_path
                file_path = lineEdit.default_file_path
                lineEdit.setText('')
                if(lineEdit.default_file_path is not None):
                    if(len(str(lineEdit.default_file_path)) < 30):
                        lineEdit.setPlaceholderText(lineEdit.default_file_path)
                    else:
                        lineEdit.setPlaceholderText('...' + str(lineEdit.default_file_path)[-30:])
                else:
                    if(lineEdit == self.select_energy_file_lineEdit):
                        lineEdit.setPlaceholderText('Optional')
                    else:
                        lineEdit.setPlaceholderText('Select...')
            else:
                if(lineEdit.previous_valid_file_path is not None):
                    file_path = QtCore.QString(lineEdit.previous_valid_file_path)
                    if(lineEdit.previous_valid_file_path != lineEdit.default_file_path):
                        lineEdit.setText(file_path)
                    else:
                        lineEdit.setText('')
                        if(len(str(lineEdit.default_file_path)) < 30):
                            lineEdit.setPlaceholderText(lineEdit.default_file_path)
                        else:
                            lineEdit.setPlaceholderText('...' + str(lineEdit.default_file_path)[-30:])
                else:
                    file_path =  None
                    lineEdit.setText('')
                    if(lineEdit == self.select_energy_file_lineEdit):
                        lineEdit.setPlaceholderText('Optional')
                    else:
                        lineEdit.setPlaceholderText('Select...')

        if(lineEdit == self.select_prim_cell_file_lineEdit):
            self.prim_cell_file_path = file_path
        elif(lineEdit == self.select_pckpts_file_lineEdit):
            self.pckpts_file_path = file_path
        elif(lineEdit == self.select_energy_file_lineEdit):
            self.energy_file_path = file_path
        elif(lineEdit == self.select_EBS_file_lineEdit):
            self.EBS_file_path = file_path


    def on_editing_output_file_lineEdit(self):
        # lineEdit.isModified() returns False unless the text has been manually changed by the user
        if(not self.select_out_figure_file_lineEdit.isModified()): 
            return

        current_file_path = self.out_figure_file_path
        new_file_path = str(self.select_out_figure_file_lineEdit.text()).strip(' .')
        if(new_file_path.startswith('file:')):
            new_file_path = new_file_path[5:]

        if(new_file_path == ''):
            self.out_figure_file_path  = None
            self.select_out_figure_file_lineEdit.setText('')
            self.select_out_figure_file_lineEdit.setPlaceholderText(self.select_out_figure_file_lineEdit.default_text)
            return

        file_format_is_valid = False
        for ext in allowed_fig_formats():
            if(new_file_path.lower().endswith(ext)):
                file_format_is_valid = True
                break
        if(not file_format_is_valid):
            new_file_path = new_file_path.strip() + '.' + set_default_fig_format(allowed_fig_formats())

        new_file_path = os.path.abspath(new_file_path)
        file_exists = os.path.isfile(new_file_path)
        is_directory = os.path.isdir(new_file_path)
        if(file_exists or is_directory): 
            reply = QtGui.QMessageBox.question(self, ' ', 'File "%s" exists. Overwrite?' % new_file_path, 
                                               QtGui.QMessageBox.Yes | QtGui.QMessageBox.No, 
                                               QtGui.QMessageBox.No)
            if reply == QtGui.QMessageBox.Yes:
                self.out_figure_file_path = QtCore.QString(new_file_path)
            else:
                if self.out_figure_file_path is not None:
                    if(str(new_file_path) == str(self.out_figure_file_path)):
                        self.out_figure_file_path = None
                    else:
                        self.out_figure_file_path = QtCore.QString(self.out_figure_file_path)
        else:
            self.out_figure_file_path = QtCore.QString(new_file_path)

        if(self.out_figure_file_path is not None):
            self.select_out_figure_file_lineEdit.setText(self.out_figure_file_path)
        else: 
            self.select_out_figure_file_lineEdit.setText('')
            self.select_out_figure_file_lineEdit.setPlaceholderText(self.select_out_figure_file_lineEdit.default_text)
        return

    def on_aspect_ratio_change(self):
        try:
            new_ar = QtCore.QString(str(abs(Fraction(str(self.aspect_ratio_lineEdit.text())).limit_denominator(max_denominator=99))))
            if(new_ar == self.default_aspect_ratio):
                new_ar = None
        except (SyntaxError, ValueError):
            if(str(self.aspect_ratio_lineEdit.text()).strip() == ''):
                new_ar = None
            else:
                new_ar = self.aspect_ratio
        except ZeroDivisionError:
            new_ar = None
        self.aspect_ratio = new_ar

        if(self.aspect_ratio is None):
            self.aspect_ratio_lineEdit.setText('')
            # The next line might look a bit odd, but it's part of the trick to overcome the lack of placeholder text in Qt4.6 and lower
            self.aspect_ratio_lineEdit.setPlaceholderText(self.aspect_ratio_lineEdit.PlaceholderText())
        else:
            self.aspect_ratio_lineEdit.setText(new_ar)

    def __validated_numeric_lineEdit(self, lineEdit, current_value, lower_bound=float("-inf"), upper_bound=float("inf")):
        try:
            new_value = float(lineEdit.text())
            if(((lower_bound is not None) and (new_value <= lower_bound)) or
               ((upper_bound is not None) and (new_value >= upper_bound))):
                raise ValueError
        except ValueError:
            if(str(lineEdit.text()).strip() == ''): # If user resets lineEdit
                new_value = None
            else:
                new_value = current_value

        if(new_value is None):
            lineEdit.setText('')
            # The next line might look a bit odd, but it's part of the trick to overcome the lack of placeholder text in Qt4.6 and lower
            lineEdit.setPlaceholderText(lineEdit.PlaceholderText())
        else:
            lineEdit.setText(str(new_value))

        return new_value

    def on_vmin_change(self):
        self.vmin = self.__validated_numeric_lineEdit(self.vmin_lineEdit, self.vmin, upper_bound=self.vmax)
    def on_vmax_change(self):
        self.vmax = self.__validated_numeric_lineEdit(self.vmax_lineEdit, self.vmax, lower_bound=self.vmin)
    def on_min_E_change(self):
        self.min_E = self.__validated_numeric_lineEdit(self.min_E_lineEdit, self.min_E, upper_bound=self.max_E)
    def on_max_E_change(self):
        self.max_E = self.__validated_numeric_lineEdit(self.max_E_lineEdit, self.max_E, lower_bound=self.min_E)
    def on_min_k_change(self):
        self.min_k = self.__validated_numeric_lineEdit(self.min_k_lineEdit, self.min_k, upper_bound=self.max_k)
    def on_max_k_change(self):
        self.max_k = self.__validated_numeric_lineEdit(self.max_k_lineEdit, self.max_k, lower_bound=self.min_k)



    def selectFile(self, button, lineEdit):
        os.chdir(str(self.last_folder)) # This is to make the open/save file dialog screens remember the last folder
        if(button == self.select_out_figure_file_Button):
            if(self.default_out_figure_file_path):
                default_out_figure_file_path = self.default_out_figure_file_path
            else:
                default_output_file_name = 'plot_EBS_BandUP.' + set_default_fig_format(allowed_fig_formats())
            allowed_file_types_string = "Images (*." + " *.".join(allowed_fig_formats()) + ")"
            file_path = str(QtGui.QFileDialog.getSaveFileName(self, self.windowTitle() + ' - Save file', default_output_file_name, allowed_file_types_string))
            if(file_path.strip()):
                self.out_figure_file_path = QtCore.QString(file_path)
                lineEdit.setText(self.out_figure_file_path)  # setText does NOT send a 'textEdited' signal. It only sends 'textChanged'
        else:
            file_path = str(QtGui.QFileDialog.getOpenFileName(self, self.windowTitle() + ' - Select file'))
            file_path = os.path.abspath(file_path)

            file_exists = os.path.isfile(file_path)
            is_directory = os.path.isdir(file_path)

            if(file_exists and not is_directory):
                lineEdit.setText(file_path)
                lineEdit.previous_valid_file_path = QtCore.QString(file_path) 

                if(button == self.select_EBS_file_Button):
                    self.EBS_file_path = file_path
                elif(button == self.select_prim_cell_file_Button):
                    self.prim_cell_file_path = file_path
                elif(button == self.select_pckpts_file_Button):
                    self.pckpts_file_path = file_path
                elif(button == self.select_energy_file_Button):
                    self.energy_file_path = file_path
   
        if(os.path.dirname(file_path).strip() and not is_directory):
            self.last_folder = QtCore.QString(os.path.dirname(file_path))
            self.update_lineEdit_completer()

 
    def onRun(self):
        args_for_plotting_tool = []
        # pushButton objects, input and output files
        def warn_file_not_selected(filetype): 
            reply = QtGui.QMessageBox.warning(self, ' ', 'The %s file could not be found.' % filetype, QtGui.QMessageBox.Ok)

        if(os.path.isfile(str(self.EBS_file_path).strip())):
            args_for_plotting_tool.append(self.EBS_file_path)
        else:
            warn_file_not_selected("EBS (BandUP's output)")
            return

        if(self.out_figure_file_path): 
            args_for_plotting_tool.append(self.out_figure_file_path)

        if(os.path.isfile(str(self.prim_cell_file_path))):
            args_for_plotting_tool += ['-pc_file', self.prim_cell_file_path]
        else:
            warn_file_not_selected('primitive cell')
            return

        if(os.path.isfile(str(self.pckpts_file_path))):
            args_for_plotting_tool += ['--kpoints_file', self.pckpts_file_path]
        else:
            warn_file_not_selected('pc-kpts file')
            return

        if(self.energy_file_path is not None):
            if(os.path.isfile(str(self.energy_file_path))):
                args_for_plotting_tool += ['-efile', self.energy_file_path]
            else:
                warn_file_not_selected('energy grid configuration file')
                return
        # comboBox objects
        if(self.colormap_comboBox.currentText().toLower() != 'default'): 
            args_for_plotting_tool += ['-cmap', self.colormap_comboBox.currentText()]
        if(self.e_fermi_color_comboBox.currentText().toLower() != 'default'): 
            args_for_plotting_tool += ['--e_fermi_linecolor', self.e_fermi_color_comboBox.currentText()]
        if(self.high_symm_lines_color_comboBox.currentText().toLower() != 'default'): 
            args_for_plotting_tool += ['--high_symm_linecolor', self.high_symm_lines_color_comboBox.currentText()]
        args_for_plotting_tool += ['-res', self.fig_resolution_comboBox.currentText()[0].toLower()]
        args_for_plotting_tool += ['--interpolation', self.interpolation_comboBox.currentText().toLower()]
        args_for_plotting_tool.append('--' + self.fig_orientation_comboBox.currentText().toLower())
        args_for_plotting_tool += ['--line_style_high_symm_points', self.high_symm_lines_style_comboBox.currentText().toLower()]
        args_for_plotting_tool += ['--line_style_E_f', self.e_fermi_line_style_comboBox.currentText().toLower()]
        # spinBox objects
        args_for_plotting_tool += ['--n_levels', self.n_levels_spinBox.text()]
        if(self.show_colorbar_checkBox.isChecked()):
            args_for_plotting_tool += ['--round_cb', self.decimal_digits_cb_spinBox.text()]
        try:
            args_for_plotting_tool += ['--line_width_E_f', float(self.e_fermi_linewidth_SpinBox.text())]
        except ValueError:
            pass
        try:
            args_for_plotting_tool += ['--line_width_high_symm_points', float(self.high_symm_linewidth_SpinBox.text())]
        except ValueError:
            pass
        try:
            args_for_plotting_tool += ['-dE', float(self.dE_spinBox.text())]
        except ValueError:
            pass
        # lineEdit objects
        if(self.aspect_ratio):
            args_for_plotting_tool += ['--aspect_ratio', self.aspect_ratio]
        else: 
            args_for_plotting_tool += ['--aspect_ratio', self.default_aspect_ratio] 
        if(self.vmin): args_for_plotting_tool += ['-vmin', self.vmin]
        if(self.vmax): args_for_plotting_tool += ['-vmax', self.vmax]
        if(self.min_E): args_for_plotting_tool += ['-emin', self.min_E]
        if(self.max_E): args_for_plotting_tool += ['-emax', self.max_E]
        if(self.min_k): args_for_plotting_tool += ['-kmin', self.min_k]
        if(self.max_k): args_for_plotting_tool += ['-kmax', self.max_k]
        # CheckBoxes
        if(self.show_figure_checkBox.isChecked()): args_for_plotting_tool.append('--show')
        if(self.save_figure_checkBox.isChecked()): 
            if(self.open_saved_file_checkBox.isChecked()):
                args_for_plotting_tool.append('--saveshow')
            else:
                args_for_plotting_tool.append('--save')
        if(not self.draw_e_fermi_checkBox.isChecked()): args_for_plotting_tool.append('--no_ef')
        if(not self.draw_hygh_symm_kpts_lines_checkBox.isChecked()): args_for_plotting_tool.append('--no_symm_lines')
        if(not self.draw_high_symm_kpts_labels_checkBox.isChecked()): args_for_plotting_tool.append('--no_symm_labels')
        if(self.show_colorbar_checkBox.isChecked()): 
            if(self.show_colorbar_label_checkBox.isChecked()):
                if(self.show_colorbar_full_label_checkBox.isChecked()):
                    args_for_plotting_tool.append('--cb_label_full')
                else:
                    args_for_plotting_tool.append('--cb_label')
        else:
            args_for_plotting_tool.append('--no_cb')

        args_for_plotting_tool = [self.plot_script] + [str(arg) for arg in args_for_plotting_tool] + ['--running_from_GUI']
        # Running
        os.chdir(str(self.folder_where_gui_has_been_called)) 
        qProcess = MyQProcess(parent=self, output_window_title=self.windowTitle() + ' - Output')
        qProcess.start(' '.join(args_for_plotting_tool))


if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = BandupPlotToolWindow()
    sys.exit(app.exec_())
