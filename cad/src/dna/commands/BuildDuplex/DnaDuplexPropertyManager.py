# Copyright 2004-2008 Nanorex, Inc.  See LICENSE file for details. 
"""
DnaDuplexPropertyManager.py

@author: Mark Sims
@version: $Id$
@copyright: 2004-2008 Nanorex, Inc.  See LICENSE file for details.

Mark 2007-10-18: 
- Created. Major rewrite of DnaGeneratorPropertyManager.py.

Ninad 2007-10-24:
- Another major rewrite to a) use EditCommand_PM superclass and b) Implement
feature to generate Dna using endpoints of a line.
"""

__author__ = "Mark"

import foundation.env as env

from dna.model.Dna_Constants import getDuplexBasesPerTurn, getDuplexRise, getDuplexLength

from utilities.Log import redmsg ##, greenmsg, orangemsg

from PyQt4.Qt import SIGNAL
from PyQt4.Qt import Qt
from PyQt4.Qt import QAction

from PM.PM_ComboBox      import PM_ComboBox
from PM.PM_DoubleSpinBox import PM_DoubleSpinBox
from PM.PM_GroupBox      import PM_GroupBox
from PM.PM_SpinBox       import PM_SpinBox
from PM.PM_LineEdit      import PM_LineEdit
from PM.PM_ToolButton    import PM_ToolButton
from PM.PM_CoordinateSpinBoxes import PM_CoordinateSpinBoxes
from PM.PM_CheckBox   import PM_CheckBox

from widgets.DebugMenuMixin import DebugMenuMixin
from command_support.EditCommand_PM import EditCommand_PM
from geometry.VQT import V

from PM.PM_Constants     import pmDoneButton
from PM.PM_Constants     import pmWhatsThisButton
from PM.PM_Constants     import pmCancelButton

from ne1_ui.WhatsThisText_for_PropertyManagers import whatsThis_DnaDuplexPropertyManager
from widgets.prefs_widgets import connect_checkbox_with_boolean_pref

from utilities.prefs_constants import dnaDuplexEditCommand_cursorTextCheckBox_angle_prefs_key
from utilities.prefs_constants import dnaDuplexEditCommand_cursorTextCheckBox_length_prefs_key
from utilities.prefs_constants import dnaDuplexEditCommand_cursorTextCheckBox_numberOfBasePairs_prefs_key
from utilities.prefs_constants import dnaDuplexEditCommand_cursorTextCheckBox_numberOfTurns_prefs_key
from utilities.prefs_constants import dnaDuplexEditCommand_showCursorTextCheckBox_prefs_key


_superclass = EditCommand_PM

class DnaDuplexPropertyManager( EditCommand_PM, DebugMenuMixin ):
    """
    The DnaDuplexPropertyManager class provides a Property Manager 
    for the B{Build > DNA > Duplex} command.

    @ivar title: The title that appears in the property manager header.
    @type title: str

    @ivar pmName: The name of this property manager. This is used to set
                  the name of the PM_Dialog object via setObjectName().
    @type name: str

    @ivar iconPath: The relative path to the PNG file that contains a
                    22 x 22 icon image that appears in the PM header.
    @type iconPath: str
    """

    title         =  "Insert DNA"
    pmName        =  title
    iconPath      =  "ui/actions/Tools/Build Structures/InsertDsDna.png"

    def __init__( self, win, editCommand ):
        """
        Constructor for the DNA Duplex property manager.
        """
        self.endPoint1 = None
        self.endPoint2 = None

        self._conformation  = "B-DNA"
        self._numberOfBases = 0
        self._basesPerTurn  = getDuplexBasesPerTurn(self._conformation)
        self._duplexRise    = getDuplexRise(self._conformation)
        self._duplexLength  = getDuplexLength(self._conformation, 
                                              self._numberOfBases)

        _superclass.__init__( self, 
                              win,
                              editCommand)


        DebugMenuMixin._init1( self )

        self.showTopRowButtons( pmDoneButton | \
                                pmCancelButton | \
                                pmWhatsThisButton)


    def connect_or_disconnect_signals(self, isConnect):
        """
        Connect or disconnect widget signals sent to their slot methods.
        This can be overridden in subclasses. By default it does nothing.
        @param isConnect: If True the widget will send the signals to the slot 
                          method. 
        @type  isConnect: boolean
        """
        if isConnect:
            change_connect = self.win.connect
        else:
            change_connect = self.win.disconnect 


        change_connect( self.conformationComboBox,
                        SIGNAL("currentIndexChanged(int)"),
                        self.conformationComboBoxChanged )

        change_connect( self.numberOfBasePairsSpinBox,
                        SIGNAL("valueChanged(int)"),
                        self.numberOfBasesChanged )

        change_connect( self.basesPerTurnDoubleSpinBox,
                        SIGNAL("valueChanged(double)"),
                        self.basesPerTurnChanged )

        change_connect( self.duplexRiseDoubleSpinBox,
                        SIGNAL("valueChanged(double)"),
                        self.duplexRiseChanged )

        change_connect(self.showCursorTextCheckBox, 
                       SIGNAL('stateChanged(int)'), 
                       self._update_state_of_cursorTextGroupBox)


    def show(self):
        """
        Overrides superclass method. 
        Show this property manager
        """
        _superclass.show(self)
        self._update_state_of_cursorTextGroupBox(
            self.showCursorTextCheckBox.isChecked())


    def ok_btn_clicked(self):
        """
        Slot for the OK button
        """   
        if self.editCommand:
            self.editCommand.preview_or_finalize_structure(previewing = False)
            ##env.history.message(self.editCommand.logMessage)        
        self.win.toolsDone()

    def cancel_btn_clicked(self):
        """
        Slot for the Cancel button.
        """
        if self.editCommand:
            self.editCommand.cancelStructure()            
        self.win.toolsCancel()

    def _update_widgets_in_PM_before_show(self):
        """
        Update various widgets  in this Property manager.
        Overrides MotorPropertyManager._update_widgets_in_PM_before_show. 
        The various  widgets , (e.g. spinboxes) will get values from the 
        structure for which this propMgr is constructed for 
        (self.editcCntroller.struct)

        @see: MotorPropertyManager._update_widgets_in_PM_before_show
        @see: self.show where it is called. 
        """       
        pass     

    def getFlyoutActionList(self): 
        """ returns custom actionlist that will be used in a specific mode 
	or editing a feature etc Example: while in movie mode, 
	the _createFlyoutToolBar method calls
	this """	


        #'allActionsList' returns all actions in the flyout toolbar 
        #including the subcontrolArea actions
        allActionsList = []

        #Action List for  subcontrol Area buttons. 
        #In this mode there is really no subcontrol area. 
        #We will treat subcontrol area same as 'command area' 
        #(subcontrol area buttons will have an empty list as their command area 
        #list). We will set  the Comamnd Area palette background color to the
        #subcontrol area.

        subControlAreaActionList =[] 

        self.exitEditCommandAction.setChecked(True)
        subControlAreaActionList.append(self.exitEditCommandAction)

        separator = QAction(self.w)
        separator.setSeparator(True)
        subControlAreaActionList.append(separator) 


        allActionsList.extend(subControlAreaActionList)

        #Empty actionlist for the 'Command Area'
        commandActionLists = [] 

        #Append empty 'lists' in 'commandActionLists equal to the 
        #number of actions in subControlArea 
        for i in range(len(subControlAreaActionList)):
            lst = []
            commandActionLists.append(lst)

        params = (subControlAreaActionList, commandActionLists, allActionsList)

        return params

    def _addGroupBoxes( self ):
        """
        Add the DNA Property Manager group boxes.
        """        

        self._pmGroupBox1 = PM_GroupBox( self, title = "Endpoints" )
        self._loadGroupBox1( self._pmGroupBox1 )

        self._pmGroupBox1.hide()

        self._pmGroupBox2 = PM_GroupBox( self, title = "Parameters" )
        self._loadGroupBox2( self._pmGroupBox2 )

        self._displayOptionsGroupBox = PM_GroupBox( self, 
                                                    title = "Display Options" )
        self._loadDisplayOptionsGroupBox( self._displayOptionsGroupBox )


    def _loadGroupBox1(self, pmGroupBox):
        """
        Load widgets in group box 3.
        """
        #Folllowing toolbutton facilitates entering a temporary DnaLineMode
        #to create a DNA using endpoints of the specified line. 
        self.specifyDnaLineButton = PM_ToolButton(
            pmGroupBox, 
            text = "Specify Endpoints",
            iconPath  = "ui/actions/Properties Manager"\
            "/Pencil.png",
            spanWidth = True                        
        )
        self.specifyDnaLineButton.setCheckable(True)
        self.specifyDnaLineButton.setAutoRaise(True)
        self.specifyDnaLineButton.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon)

        #EndPoint1 and endPoint2 coordinates. These widgets are hidden 
        # as of 2007- 12 - 05
        self._endPoint1SpinBoxes = PM_CoordinateSpinBoxes(pmGroupBox, 
                                                          label = "End Point 1")
        self.x1SpinBox = self._endPoint1SpinBoxes.xSpinBox
        self.y1SpinBox = self._endPoint1SpinBoxes.ySpinBox
        self.z1SpinBox = self._endPoint1SpinBoxes.zSpinBox

        self._endPoint2SpinBoxes = PM_CoordinateSpinBoxes(pmGroupBox, 
                                                          label = "End Point 2")
        self.x2SpinBox = self._endPoint2SpinBoxes.xSpinBox
        self.y2SpinBox = self._endPoint2SpinBoxes.ySpinBox
        self.z2SpinBox = self._endPoint2SpinBoxes.zSpinBox

        self._endPoint1SpinBoxes.hide()
        self._endPoint2SpinBoxes.hide()

    def _loadGroupBox2(self, pmGroupBox):
        """
        Load widgets in group box 4.
        """

        self.conformationComboBox  = \
            PM_ComboBox( pmGroupBox,
                         label         =  "Conformation:", 
                         choices       =  ["B-DNA"],
                         setAsDefault  =  True)

        dnaModelChoices = ['PAM3', 'PAM5']
        self.dnaModelComboBox = \
            PM_ComboBox( pmGroupBox,     
                         label         =  "Model:", 
                         choices       =  dnaModelChoices,
                         setAsDefault  =  True)


        self.basesPerTurnDoubleSpinBox  =  \
            PM_DoubleSpinBox( pmGroupBox,
                              label         =  "Bases per turn:",
                              value         =  self._basesPerTurn,
                              setAsDefault  =  True,
                              minimum       =  8.0,
                              maximum       =  20.0,
                              decimals      =  2,
                              singleStep    =  0.1 )

        self.duplexRiseDoubleSpinBox  =  \
            PM_DoubleSpinBox( pmGroupBox,
                              label         =  "Rise:",
                              value         =  self._duplexRise,
                              setAsDefault  =  True,
                              minimum       =  2.0,
                              maximum       =  4.0,
                              decimals      =  3,
                              singleStep    =  0.01 )

        # Strand Length (i.e. the number of bases)
        self.numberOfBasePairsSpinBox = \
            PM_SpinBox( pmGroupBox, 
                        label         =  "Base pairs:", 
                        value         =  self._numberOfBases,
                        setAsDefault  =  False,
                        minimum       =  0,
                        maximum       =  10000 )

        self.numberOfBasePairsSpinBox.setDisabled(True)   

        # Duplex Length
        self.duplexLengthLineEdit  =  \
            PM_LineEdit( pmGroupBox,
                         label         =  "Duplex length: ",
                         text          =  "0.0 Angstroms",
                         setAsDefault  =  False)

        self.duplexLengthLineEdit.setDisabled(True)        


    def _loadDisplayOptionsGroupBox(self, pmGroupBox):
        """
        Load widgets in group box 4.
        """

        self.showCursorTextCheckBox = \
            PM_CheckBox( 
                pmGroupBox,
                text  = "Show Cursor Text",
                widgetColumn = 0,
                state        = Qt.Checked)

        self._cursorTextGroupBox = PM_GroupBox(pmGroupBox, 
                                               title = 'Cursor text options:')

        self._loadCursorTextCheckBoxes(self._cursorTextGroupBox)
        self._connect_cursorTextCheckBoxes()


        self._rubberbandLineGroupBox = PM_GroupBox(
            pmGroupBox,
            title = 'Rubber band line:')

        dnaLineChoices = ['Ribbons', 'Ladder']
        self.dnaRubberBandLineDisplayComboBox = \
            PM_ComboBox( self._rubberbandLineGroupBox ,     
                         label         =  " Display as:", 
                         choices       =  dnaLineChoices,
                         setAsDefault  =  True)

        self.lineSnapCheckBox = \
            PM_CheckBox(self._rubberbandLineGroupBox ,
                        text         = 'Enable line snap' ,
                        widgetColumn = 1,
                        state        = Qt.Checked
                    )

    def _loadCursorTextCheckBoxes(self, pmGroupBox):
        """
         Load various checkboxes that allow custom cursor texts. Subclasses 
         can override this method. Default implementation adds following 
         checkboxes
         """        
        self.cursorTextCheckBox_numberOfBasePairs = \
            PM_CheckBox( 
                pmGroupBox,
                text  = "Number Of base pairs",
                widgetColumn = 1,
                state        = Qt.Checked)

        self.cursorTextCheckBox_numberOfTurns = \
            PM_CheckBox( 
                pmGroupBox,
                text  = "Number of turns",
                widgetColumn = 1,
                state        = Qt.Checked)

        self.cursorTextCheckBox_length = \
            PM_CheckBox( 
                pmGroupBox,
                text  = "Duplex Length",
                widgetColumn = 1,
                state        = Qt.Checked)

        self.cursorTextCheckBox_angle = \
            PM_CheckBox( 
                pmGroupBox,
                text  = "Angle information",
                widgetColumn = 1,
                state        = Qt.Checked)


    def _connect_cursorTextCheckBoxes(self):
        """
        Default implementation does nothing. Its overridden in subclasses
        Connect the cursor text checkboxes with the preference keys. 
        @see: self._loadDisplayOptionsGroupBox()        
        """
        connect_checkbox_with_boolean_pref(
            self.showCursorTextCheckBox , 
            dnaDuplexEditCommand_showCursorTextCheckBox_prefs_key)

        connect_checkbox_with_boolean_pref(
            self.cursorTextCheckBox_numberOfBasePairs , 
            dnaDuplexEditCommand_cursorTextCheckBox_numberOfBasePairs_prefs_key)

        connect_checkbox_with_boolean_pref(
            self.cursorTextCheckBox_numberOfTurns , 
            dnaDuplexEditCommand_cursorTextCheckBox_numberOfTurns_prefs_key)

        connect_checkbox_with_boolean_pref(
            self.cursorTextCheckBox_length , 
            dnaDuplexEditCommand_cursorTextCheckBox_length_prefs_key)

        connect_checkbox_with_boolean_pref(
            self.cursorTextCheckBox_angle , 
            dnaDuplexEditCommand_cursorTextCheckBox_angle_prefs_key)


    def _addToolTipText(self):
        """
        Tool Tip text for widgets in the DNA Property Manager.  
        """
        pass

    def conformationComboBoxChanged( self, inIndex ):
        """
        Slot for the Conformation combobox. It is called whenever the
        Conformation choice is changed.

        @param inIndex: The new index.
        @type  inIndex: int
        """
        conformation  =  self.conformationComboBox.currentText()

        if conformation == "B-DNA":
            self.basesPerTurnDoubleSpinBox.setValue("10.0")

        elif conformation == "Z-DNA":
            self.basesPerTurnDoubleSpinBox.setValue("12.0")

        else:
            msg = redmsg("conformationComboBoxChanged(): \
                         Error - unknown DNA conformation. Index = "+ inIndex)
            env.history.message(msg)

        self.duplexLengthSpinBox.setSingleStep(getDuplexRise(conformation))

    def numberOfBasesChanged( self, numberOfBases ):
        """
        Slot for the B{Number of Bases} spinbox.
        """
        # Update the Duplex Length lineEdit widget.
        text = str(getDuplexLength(self._conformation, 
                                   numberOfBases,
                                   self._duplexRise)) \
             + " Angstroms"
        self.duplexLengthLineEdit.setText(text)
        return

    def basesPerTurnChanged( self, basesPerTurn ):
        """
        Slot for the B{Bases per turn} spinbox.
        """
        self.editCommand.basesPerTurn = basesPerTurn
        self._basesPerTurn = basesPerTurn
        return

    def duplexRiseChanged( self, rise ):
        """
        Slot for the B{Rise} spinbox.
        """
        self.editCommand.duplexRise = rise
        self._duplexRise = rise
        return

    def _update_state_of_cursorTextGroupBox(self, enable):
        if enable:
            self._cursorTextGroupBox.setEnabled(True)
        else:
            self._cursorTextGroupBox.setEnabled(False)


    def getParameters(self):
        """
        Return the parameters from this property manager
        to be used to create the DNA duplex. 
        @return: A tuple containing the parameters
        @rtype: tuple
        @see: L{DnaDuplex_EditCommand._gatherParameters} where this is used 
        """
        numberOfBases = self.numberOfBasePairsSpinBox.value()
        dnaForm  = str(self.conformationComboBox.currentText())
        basesPerTurn = self.basesPerTurnDoubleSpinBox.value()
        duplexRise = self.duplexRiseDoubleSpinBox.value()

        dnaModel = str(self.dnaModelComboBox.currentText())

        # First endpoint (origin) of DNA duplex
        x1 = self.x1SpinBox.value()
        y1 = self.y1SpinBox.value()
        z1 = self.z1SpinBox.value()

        # Second endpoint (direction vector/axis) of DNA duplex.
        x2 = self.x2SpinBox.value()
        y2 = self.y2SpinBox.value()
        z2 = self.z2SpinBox.value()

        if not self.endPoint1:
            self.endPoint1 = V(x1, y1, z1)
        if not self.endPoint2:
            self.endPoint2 = V(x2, y2, z2)

        return (numberOfBases, 
                dnaForm,
                dnaModel,
                basesPerTurn,
                duplexRise,
                self.endPoint1, 
                self.endPoint2)

    def _addWhatsThisText(self):
        """
        What's This text for widgets in this Property Manager.  
        """
        whatsThis_DnaDuplexPropertyManager(self)

