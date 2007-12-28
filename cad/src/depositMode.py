# Copyright 2004-2007 Nanorex, Inc.  See LICENSE file for details. 
"""
depositMode.py -- Build Atoms mode.

$Id$
"""
__author__ = "Mark" 
    # Josh was the original author, but this has been largely rewritten by Mark. mark 060214.

import os
import math # only for pi
from Numeric import dot

from OpenGL.GL import GL_FALSE
from OpenGL.GL import glDepthMask
from OpenGL.GL import GL_TRUE
from OpenGL.GL import GL_LIGHTING
from OpenGL.GL import glColor4fv
from OpenGL.GL import GL_BLEND
from OpenGL.GL import GL_ONE_MINUS_SRC_ALPHA
from OpenGL.GL import GL_SRC_ALPHA
from OpenGL.GL import glBlendFunc
from OpenGL.GL import glTranslatef
from OpenGL.GL import glRotatef
from OpenGL.GL import GL_QUADS
from OpenGL.GL import glBegin
from OpenGL.GL import glVertex
from OpenGL.GL import glEnd
from OpenGL.GL import glDisable
from OpenGL.GL import glEnable
from OpenGL.GL import glPushMatrix
from OpenGL.GL import glPopMatrix

from OpenGL.GLU import gluUnProject

from PyQt4 import QtGui
from PyQt4.Qt import Qt

from PyQt4.Qt import QSize
from PyQt4.Qt import SIGNAL


import env
import platform
import changes
from PlatformDependent import fix_plurals

from chunk      import Chunk
from chem       import Atom
from chem       import oneUnbonded
from elements   import Singlet
from VQT        import Q, A, norm, twistor

from drawer     import drawline

from icon_utilities import geticon
from Group      import Group
from Utility    import Node
from pastables  import is_pastable
from pastables  import find_hotspot_for_pasting

from ops_copy        import copied_nodes_for_DND
from Select_GraphicsMode      import DRAG_STICKINESS_LIMIT
from selectAtomsMode import selectAtomsMode

from shape import get_selCurve_color

from bonds           import bond_atoms, bond_at_singlets
from bond_constants  import V_SINGLE

from debug import print_compact_stack
from debug import print_compact_traceback

from constants import elemKeyTab
from constants import diINVISIBLE
from constants import diTUBES

from bond_constants import btype_from_v6
from bond_constants import V_DOUBLE
from bond_constants import V_GRAPHITE
from bond_constants import V_TRIPLE
from bond_constants import V_AROMATIC

from prefs_constants import buildModeSelectAtomsOfDepositedObjEnabled_prefs_key
from prefs_constants import buildModeWaterEnabled_prefs_key
from prefs_constants import buildModeHighlightingEnabled_prefs_key
from prefs_constants import keepBondsDuringTransmute_prefs_key

from utilities.Log import orangemsg, redmsg, greenmsg, quote_html

from BuildAtomsPropertyManager import BuildAtomsPropertyManager

_superclass = selectAtomsMode

class depositMode(selectAtomsMode):
    """
    This class is used to manually add atoms to create any structure.
    Users know it as "Build Atoms".
    """
    
    # class constants
    gridColor = 74/255.0, 186/255.0, 226/255.0
    commandName = 'DEPOSIT' 
    msg_commandName = "Build Mode" # Capitalized 'Mode'. Fixes bugs 612-1.2 and 1.3. mark 060323
    default_mode_status_text = "Mode: Build Atoms"
    featurename = "Build Atoms Mode"

    highlight_singlets = True # Always highlight singlets in depositMode. Mark 060220.

    def __init__(self, glpane):
                
        _superclass.__init__(self, glpane)
                                
        self.pastables_list = [] #k not needed here?
        self.water_enabled = env.prefs[buildModeWaterEnabled_prefs_key] # mark 060203.
            # if True, only atoms and bonds above the water surface can be 
            # highlighted and selected.
            # if False, all atoms and bonds can be highlighted and selected, and the water 
            # surface is not displayed.
        self.hover_highlighting_enabled = env.prefs[buildModeHighlightingEnabled_prefs_key]
            # Moved here as part of fix for bug 1620.  mark 060322
    # methods related to entering this mode         
    dont_update_gui = True
        
    
    def Enter(self):
        
        self._init_flyoutActions()
                        
        _superclass.Enter(self) # this calls self.reset_drag_vars(), which itself calls the super version
        
        #self.o.assy.permit_pick_atoms() #bruce 050517 revised API of this call
            # moved permit_pick_atoms() to selectAtomsMode.Enter().  mark 060219.
        self.pastable = None #k would it be nicer to preserve it from the past??
            # note, this is also done redundantly in init_gui.
        self.pastables_list = [] # should be ok, since update_gui comes after this...
        ## removed this since it's redundant [bruce 060726]: self.reset_drag_vars()
        
        
    def reset_drag_vars(self):
        # called in Enter and at start of (super's) leftDown
        _superclass.reset_drag_vars(self)
        
        self.pivot = None
        self.pivax = None
        self.line = None
            # endpoints of the white line drawn between the cursor and a bondpoint when 
            # dragging a singlet.
        self.transdepositing = False
            # used to suppress multiple win_updates and history msgs when trans-depositing.
        
    def init_gui(self):
        """
        Do changes to the GUI while entering this mode. This includes opening 
        the property manager, updating the command explorer , connecting widget 
        slots etc. 
        
        Called once each time the mode is entered; should be called only by code 
        in modes.py
        
        @see: L{self.restore_gui}
        """
        
        # Gui actions such  Nanotubegenerator are disabled while in the 
        # Build mode 
        self.enable_gui_actions(False)
        
        self.dont_update_gui = True # redundant with Enter, I think; changed below
        # (the possible orders of calling all these mode entering/exiting
        #  methods is badly in need of documentation, if not cleanup...
        #  [says bruce 050121, who is to blame for this])
        
        #important to check for old propMgr object. Reusing propMgr object 
        #significantly improves the performance.
        if not self.propMgr:
            self.propMgr = BuildAtomsPropertyManager(self)
            #@bug BUG: following is a workaround for bug 2494.
            #This bug is mitigated as propMgr object no longer gets recreated
            #for modes -- niand 2007-08-29
            changes.keep_forever(self.propMgr)  
            
        self.propMgr.show()
        
        self.updateCommandToolbar(bool_entering = True)
        
        
        if self.depositAtomsAction.isChecked():
            self.activateAtomsTool()
        elif self.transmuteBondsAction.isChecked():
            self.activateBondsTool()
            
        self.w.toolsDepositAtomAction.setChecked(True)  
        
        self.pastable = None # by bruce 041124, for safety
        self.bondclick_v6 = None        
        self.update_bond_buttons()
        
        self.connect_or_disconnect_signals(True)      
        
        self.dont_update_gui = False
        
        self.propMgr.updateMessage()
        
        # The caller will now call update_gui(); we rely on that [bruce 050122]
        return
    
    def enable_gui_actions(self, bool):
        """
        Enable or disable some gui actions depending on 
        whether user is entering or leaving the mode
        """
        self.w.insertNanotubeAction.setEnabled(bool)
        self.w.buildDnaAction.setEnabled(bool)
        self.w.insertGrapheneAction.setEnabled(bool)
        self.w.toolsCookieCutAction.setEnabled(bool)
        #@@This should also contain HeteroJunctionAction. (in general Plugin actions)
    
    def _init_flyoutActions(self):
        """
        Define flyout toolbar actions for this mode.
        """
        #@NOTE: In Build mode, some of the actions defined in this method are also 
        #used in Build Atoms PM. (e.g. bond actions) So probably better to rename 
        #it as _init_modeActions. Not doing that change in mmkit code cleanup 
        #commit(other modes still implement a method by same name)-ninad20070717
                
        self.exitModeAction = QtGui.QWidgetAction(self.w)
        self.exitModeAction.setText("Exit Atoms")
        self.exitModeAction.setIcon(geticon('ui/actions/Toolbars/Smart/Exit'))
        self.exitModeAction.setCheckable(True)
        self.exitModeAction.setChecked(True)    
        
        #Following Actions are added in the Flyout toolbar. 
        #Defining them outside that method as those are being used
        #by the subclasses of deposit mode (testmode.py as of 070410) -- ninad
                
        self.depositAtomsAction = QtGui.QWidgetAction(self.w)
        self.depositAtomsAction.setText("Atoms Tool")
        self.depositAtomsAction.setIcon(geticon(
            'ui/actions/Toolbars/Smart/Deposit_Atoms'))
        self.depositAtomsAction.setCheckable(True)
        self.depositAtomsAction.setChecked(True)
        
                
        self.transmuteBondsAction = QtGui.QWidgetAction(self.w)
        self.transmuteBondsAction.setText("Bonds Tool")
        self.transmuteBondsAction.setIcon(geticon(
            'ui/actions/Toolbars/Smart/Transmute_Bonds'))
        self.transmuteBondsAction.setCheckable(True)
        
        self.subControlActionGroup = QtGui.QActionGroup(self.w)
        self.subControlActionGroup.setExclusive(True)   
        self.subControlActionGroup.addAction(self.depositAtomsAction)   
        ##self.subControlActionGroup.addAction(self.propMgr.transmuteAtomsAction)
        self.subControlActionGroup.addAction(self.transmuteBondsAction)
        
        self.bondToolsActionGroup = QtGui.QActionGroup(self.w)
        self.bondToolsActionGroup.setExclusive(True)
                
        self.bond1Action = QtGui.QWidgetAction(self.w)  
        self.bond1Action.setText("Single")
        self.bond1Action.setIcon(geticon("ui/actions/Toolbars/Smart/bond1.png"))
            
        self.bond2Action = QtGui.QWidgetAction(self.w)  
        self.bond2Action.setText("Double")
        self.bond2Action.setIcon(geticon("ui/actions/Toolbars/Smart/bond2.png"))
        
        self.bond3Action = QtGui.QWidgetAction(self.w)  
        self.bond3Action.setText("Triple")
        self.bond3Action.setIcon(geticon("ui/actions/Toolbars/Smart/bond3.png"))
        
        self.bondaAction = QtGui.QWidgetAction(self.w)  
        self.bondaAction.setText("Aromatic")
        self.bondaAction.setIcon(geticon("ui/actions/Toolbars/Smart/bonda.png"))
        
        self.bondgAction = QtGui.QWidgetAction(self.w)  
        self.bondgAction.setText("Graphitic")
        self.bondgAction.setIcon(geticon("ui/actions/Toolbars/Smart/bondg.png"))
        
        self.cutBondsAction = QtGui.QWidgetAction(self.w)  
        self.cutBondsAction.setText("Cut Bonds")
        self.cutBondsAction.setIcon(geticon("ui/actions/Tools/Build Tools/Cut_Bonds"))
        
        for action in [self.bond1Action, 
                       self.bond2Action, 
                       self.bond3Action,
                       self.bondaAction,
                       self.bondgAction,
                       self.cutBondsAction  
                       ]:
            self.bondToolsActionGroup.addAction(action)
            action.setCheckable(True)
                    
        
        self.transmuteAtomsAction = QtGui.QWidgetAction(self.w)
        self.transmuteAtomsAction.setText("Transmute Atoms")
        self.transmuteAtomsAction.setIcon(geticon(
            'ui/actions/Toolbars/Smart/Transmute_Atoms'))       
        self.transmuteAtomsAction.setCheckable(False)
           

    def connect_or_disconnect_signals(self, connect): #bruce 050728
        """
        Connect or disconnect widget signals sent to their slot methods.
        @param isConnect: If True the widget will send the signals to the slot 
                          method. 
        @type  isConnect: boolean
        """
        if connect:
            change_connect = self.w.connect
        else:
            change_connect = self.w.disconnect
        
        
        #Atom , Bond Tools Groupbox
        change_connect(self.bondToolsActionGroup,
                       SIGNAL("triggered(QAction *)"), self.changeBondTool)
                
        
        change_connect(self.transmuteAtomsAction,
                        SIGNAL("triggered()"),self.transmutePressed)
                       
                
        change_connect(self.exitModeAction, SIGNAL("triggered()"), 
                       self.w.toolsDone)
        
        change_connect(self.subControlActionGroup, 
                       SIGNAL("triggered(QAction *)"),
                       self.updateCommandToolbar)
        
        change_connect(self.transmuteBondsAction, 
                       SIGNAL("triggered()"), 
                       self.activateBondsTool)
        
        change_connect(self.depositAtomsAction, 
                       SIGNAL("triggered()"), 
                       self.activateAtomsTool)
        
        #Connect or disconnect signals in property manager      
        self.propMgr.connect_or_disconnect_signals(connect)
                                
        return
    
    def set_selection_filter(self, enabled):
        """
        Set/ Unset selection filter. 
        @param enabled: boolean that decides whether to turn 
                        selection filter on or off. 
        @type enabled: boolean
        """
        self.propMgr.set_selection_filter(enabled) 
    
            
    def getFlyoutActionList(self): #Ninad 070126
        """
        Returns a tuple that contains mode spcific actionlists in the 
        added in the flyout toolbar of the mode. 
        CommandToolbar._createFlyoutToolBar method calls this 
        @return: params: A tuple that contains 3 lists: 
        (subControlAreaActionList, commandActionLists, allActionsList)
        """
        
        #ninad070330 This implementation may change in future. 
        
        #'allActionsList' returns all actions in the flyout toolbar 
        #including the subcontrolArea actions. 
        allActionsList = []
        #Action List for  subcontrol Area buttons. 
        #For now this list is just used to set a different palette to thisaction
        #buttons in the toolbar
        subControlAreaActionList =[] 
        
                
        #Append subcontrol area actions to  subControlAreaActionList
        #The 'Exit button' althought in the subcontrol area, would 
        #look as if its in the Control area because of the different color palette 
        #and the separator after it. This is intentional.
        subControlAreaActionList.append(self.exitModeAction)
        separator1 = QtGui.QAction(self.w)
        separator1.setSeparator(True)
        subControlAreaActionList.append(separator1) 
        
        subControlAreaActionList.append(self.depositAtomsAction)        
        ##subControlAreaActionList.append(self.propMgr.transmuteAtomsAction)
        subControlAreaActionList.append(self.transmuteBondsAction)      
        separator = QtGui.QAction(self.w)
        separator.setSeparator(True)
        subControlAreaActionList.append(separator) 
        
        #Also add the subcontrol Area actions to the 'allActionsList'
        for a in subControlAreaActionList:
            allActionsList.append(a)    
        ##actionlist.append(self.w.modifyAdjustSelAction)
        ##actionlist.append(self.w.modifyAdjustAllAction)
        
        #Ninad 070330:
        #Command Actions : These are the actual actions that will respond the 
        #a button pressed in the 'subControlArea (if present). 
        #Each Subcontrol area button can have its own 'command list' 
        #The subcontrol area buuton and its command list form a 'key:value pair 
        #in a python dictionary object
        #In Build mode, as of 070330 we have 3 subcontrol area buttons 
        #(or 'actions)'
        commandActionLists = [] 
        
        #Append empty 'lists' in 'commandActionLists equal to the 
        #number of actions in subControlArea 
        for i in range(len(subControlAreaActionList)):
            lst = []
            commandActionLists.append(lst)
        
        #Command list for the subcontrol area button 'Atoms Tool'
        #For others, this list will remain empty for now -- ninad070330 
        depositAtomsCmdLst = []
        depositAtomsCmdLst.append(self.w.modifyHydrogenateAction)
        depositAtomsCmdLst.append(self.w.modifyDehydrogenateAction)
        depositAtomsCmdLst.append(self.w.modifyPassivateAction)
        separatorAfterPassivate = QtGui.QAction(self.w)
        separatorAfterPassivate.setSeparator(True)
        depositAtomsCmdLst.append(separatorAfterPassivate)
        depositAtomsCmdLst.append(self.transmuteAtomsAction)    
        separatorAfterTransmute = QtGui.QAction(self.w)
        separatorAfterTransmute.setSeparator(True)
        depositAtomsCmdLst.append(separatorAfterTransmute)
        depositAtomsCmdLst.append(self.w.modifyDeleteBondsAction)
        depositAtomsCmdLst.append(self.w.modifySeparateAction)
        depositAtomsCmdLst.append(self.w.makeChunkFromSelectedAtomsAction)
                        
        commandActionLists[2].extend(depositAtomsCmdLst)
        
        ##for action in self.w.buildToolsMenu.actions():
            ##commandActionLists[2].append(action)
        
        # Command list for the subcontrol area button 'Bonds Tool'
        # For others, this list will remain empty for now -- ninad070405 
        bondsToolCmdLst = []
        bondsToolCmdLst.append(self.bond1Action)
        bondsToolCmdLst.append(self.bond2Action)
        bondsToolCmdLst.append(self.bond3Action)
        bondsToolCmdLst.append(self.bondaAction)
        bondsToolCmdLst.append(self.bondgAction)
        bondsToolCmdLst.append(self.cutBondsAction)
        commandActionLists[3].extend(bondsToolCmdLst)
                            
        params = (subControlAreaActionList, commandActionLists, allActionsList)
        
        return params
    
    def updateCommandToolbar(self, bool_entering = True):
        """
        Update the command toolbar.
        """        
        obj = self
        self.w.commandToolbar.updateCommandToolbar(self.w.toolsDepositAtomAction,
                                                   obj, 
                                                   entering = bool_entering)
        return
    
    def activateAtomsTool(self):
        """
        Activate the atoms tool of the build chunks mode 
        hide only the Atoms Tools groupbox in the Build chunks Property manager
        and show all others the others.
        """
        self.propMgr.bondToolsGroupBox.hide()
        
        for grpbox in self.propMgr.previewGroupBox, self.propMgr.elementChooser:
            grpbox.show()
        
        self.propMgr.pw.propertyManagerScrollArea.ensureWidgetVisible(
            self.propMgr.headerFrame)
        
        self.setAtom()
        
        self.propMgr.updateMessage()
                
    def activateBondsTool(self):
        """
        Activate the bond tool of the build chunks mode 
        Show only the Bond Tools groupbox in the Build chunks Property manager
        and hide the others.
        """
        self.bond1Action.setChecked(True)
        self.changeBondTool(self.bond1Action)
                        
        for grpbox in self.propMgr.previewGroupBox, self.propMgr.elementChooser:
            grpbox.hide()
                        
        self.propMgr.bondToolsGroupBox.show()
        
        bondToolActions =  self.bondToolsActionGroup.actions()
        for btn in self.propMgr.bondToolButtonRow.buttonGroup.buttons():
            btnId = self.propMgr.bondToolButtonRow.buttonGroup.id(btn)
            action = bondToolActions[btnId]
            action.setCheckable(True)
            btn.setIconSize(QSize(24,24))
            btn.setDefaultAction(action)
        
        self.propMgr.pw.propertyManagerScrollArea.ensureWidgetVisible(
            self.propMgr.headerFrame)
                
        self.propMgr.updateMessage()
    
    def update_selection_filter_list(self):
        """
        """
        self.propMgr.update_selection_filter_list()
                   
    def update_bond_buttons(self): 
        """
        make the dashboard one-click-bond-changer state buttons match whatever 
        is stored in self.bondclick_v6
        """
        #bruce 050728 (should this be used more widely?); revised 050831
        
        #Notes:
        # In A8, self.bond1Btn was self.w.depositAtomDashboard.build1Btn and 
        #like that. Since the dashboard will be moved to 
        #Property Manager, gradually, all self.w.depositAtomDashboard calls 
        #will be changed to sel.MMKit calls. 
        #Also note that , it may even be called by a different name instead of 
        # MMKit (e.g. BuildPropertyManager which might
        #be called as self.propMgr.pw.blahblah where self.propMgr.pw = active 
        #part window. This comment is subjected to revision - Ninad 061214
        
        self.bond1Action.setChecked( self.bondclick_v6 == V_SINGLE)
        self.bond2Action.setChecked( self.bondclick_v6 == V_DOUBLE)
        self.bond3Action.setChecked( self.bondclick_v6 == V_TRIPLE)
        self.bondaAction.setChecked( self.bondclick_v6 == V_AROMATIC)
        self.bondgAction.setChecked( self.bondclick_v6 == V_GRAPHITE)
        
        #####@@@@@ else set the Atom Tool on?? [bruce 060702 comment]
        return
    
    def update_gui(self): #bruce 050121 heavily revised this [called by basicMode.UpdateDashboard]
        """
        #doc...
        can be called many times during the mode;
        should be called only by code in modes.py
        """
##        if not self.isCurrentCommand():
##            print "update_gui returns since not self.isCurrentCommand"
##            return #k can this ever happen? yes, when the mode is entered!
##            # this was preventing the initial update_gui in _enterMode from running...
        
        # avoid unwanted recursion [bruce 041124]
        # [bruce 050121: this is not needed for reason it was before,
        #  but we'll keep it (in fact improve it) in case it's needed now
        #  for new reasons -- i don't know if it is, but someday it might be]
        
        
        if self.dont_update_gui:
            pass ## print "update_gui returns since self.dont_update_gui" ##@@@@
            # Getting msg after depositing an atom, then selecting a bondpoint 
            # and "Select Hotspot and Copy" from the GLPane menu.
            # Is it a bug??? Mark 051212.
            # bruce 060412 replies: I don't know; it might be. Perhaps we should
            # do what MMKit does as of today,
            # and defer all UpdateDashboard actions until another event handler
            # (here, or better in basicMode).
            # But for now I'll disable the debug print and we can defer this 
            # issue unless it becomes suspected
            # in specific bugs.
            return
        # now we know self.dont_update_gui == False, so ok that we reset it to 
        # that below (I hope)
        self.dont_update_gui = True
        try:
            self.update_gui_0()
        except:
            print_compact_traceback("exception from update_gui_0: ")
        self.dont_update_gui = False
        self.resubscribe_to_clipboard_members_changed()
        return

    def update_gui_0(self): #bruce 050121 split this out and heavily revised it
        # [Warning, bruce 050316: when this runs, new clipboard items might not
        # yet have
        # their own Part, or the correct Part! So this code should not depend
        # on the .part member of any nodes it uses. If this matters, a quick
        # (but inefficient) fix would be to call that method right here...
        # except that it might not be legal to do so! Instead, we'd probably 
        # need
        # to arrange to do the actual updating (this method) only at the end of
        # the current user event. We'll need that ability pretty soon for other
        # reasons (probably for Undo), so it's ok if we need it a bit sooner.]
        
        # Subclasses update the contents of self.propMgr.clipboardGroupBox
        # (Note; earlier depositMode used to update self.w.pasteComboBox items,
        # but this implementation has been changed since 2007-09-04 after 
        # introduction of L{PasteMode}) 
        # to match the set of pastable objects on the clipboard,
        # which is cached in pastables_list for use,
        # and update the current item to be what it used to be (if that is
        # still available in the list), else the last item (if there are any 
        # items).

        # First, if self.pastable is None, set it to the current value from
        # the spinbox and prior list, in case some other code set it to None
        # when it set depositState to 'Atoms' or 'Library' (tho I don't think 
        # that other code really
        # needs to do that). This is safe even if called "too early". But if 
        # it's
        # already set, don't change it, so callers of UpdateDashboard can set it
        # to the value they want, even if that value is not yet in the spinbox
        # (see e.g. setHotSpot_mainPart).
        if not self.pastable:
            self.update_pastable()
        
        # update the list of pastable things - candidates are all objects
        # on the clipboard
        members = self.o.assy.shelf.members[:]
        ## not needed or correct since some time ago [bruce 050110]:
        ##   members.reverse() # bruce 041124 -- model tree seems to have them backwards
        self.pastables_list = filter( is_pastable, members)

        # experiment 050122: mark the clipboard items to influence their appearance
        # in model tree... not easy to change their color, so maybe we'll let this
        # change their icon (just in chunk.py for now). Not yet done. We'd like the
        # one equal to self.pastable (when self.depositState == 'Clipboard' and this is current mode)
        # to look the most special. But that needs to be recomputed more often
        # than this runs. Maybe we'll let the current mode have an mtree-icon-filter??
        # Or, perhaps, let it modify the displayed text in the mtree, from node.name. ###@@@
        for mem in members:
            mem._note_is_pastable = False # set all to false...
        for mem in self.pastables_list:
            mem._note_is_pastable = True # ... then change some of those to true
        
        if not self.pastables_list:
            # insert a text label saying why spinbox is empty [bruce 041124]
            if members:
                whynot = "(no clips are pastable)" # this text should not be longer than the one below, for now
            else:
                whynot = "(clipboard is empty)"            
            self.pastable = None
        else:
            # choose the best current item for self.pastable and spinbox position
            # (this is the same pastable as before, if it's still available)
            if self.pastable not in self.pastables_list: # (works even if self.pastable is None)
                self.pastable = self.pastables_list[-1]
                # use the last one (presumably the most recently added)
                # (no longer cares about selection of clipboard items -- bruce 050121)
            assert self.pastable # can fail if None is in the list or "not in" doesn't work right for None
               
        #e future: if model tree indicates self.pastable somehow, e.g. by color of
        # its name, update it. (It might as well also show "is_pastables" that way.) ###@@@ good idea...
        
        return
        
    def clipboard_members_changed(self, clipboard): #bruce 050121
        """
        we'll subscribe this method to changes to shelf.members, if possible
        """
        if self.isCurrentCommand():
            self.UpdateDashboard()
                #e ideally we'd set an inval flag and call that later, but when?
                # For now, see if it works this way. (After all, the old code called
                # UpdateDashboard directly from certain Node or Group methods.)
            ## call this from update_gui (called by UpdateDashboard) instead,
            ## so it will happen the first time we're setting it up, too:
            ## self.resubscribe_to_clipboard_members_changed()
            self.propMgr.update_clipboard_items() # Fixes bugs 1569, 1570, 1572 and 1573. mark 060306.
                # Note and bugfix, bruce 060412: doing this now was also causing traceback bugs 1726, 1629,
                # and the traceback part of bug 1677, and some related (perhaps unreported) bugs.
                # The problem was that this is called during pasteBond's addmol (due to its addchild), before it's finished,
                # at a time when the .part structure is invalid (since the added mol's .part has not yet been set).
                # To fix bugs 1726, 1629 and mitigate bug 1677, I revised the interface to MMKit.update_clipboard_items
                # (in the manner which was originally recommented in call_after_next_changed_members's docstring) 
                # so that it only sets a flag and updates (triggering an MMKit repaint event), deferring all UI effects to
                # the next MMKit event.
        return

    def resubscribe_to_clipboard_members_changed(self):
        try:
            ###@@@@ need this to avoid UnboundLocalError: local variable 'shelf' referenced before assignment
            # but that got swallowed the first time we entered mode!
            # but i can't figure out why, so neverind for now [bruce 050121]
            shelf = self.o.assy.shelf
            shelf.call_after_next_changed_members # does this method exist?
        except AttributeError:
            # this is normal, until I commit new code to Utility and model tree! [bruce 050121]
            pass
        except:#k should not be needed, but I'm not positive, in light of bug-mystery above
            raise
        else:
            shelf = self.o.assy.shelf
            func = self.clipboard_members_changed
            shelf.call_after_next_changed_members(func, only_if_new = True)
                # note reversed word order in method names (feature, not bug)
        return
    
    # methods related to exiting this mode [bruce 040922 made these from
    # old Done method, and added new code; there was no Flush method]

    def haveNontrivialState(self):
        return False

    def StateDone(self):
        return None
    # we never have undone state, but we have to implement this method,
    # since our haveNontrivialState can return True

    def StateCancel(self):
        # to do this correctly, we'd need to remove the atoms we added
        # to the assembly; we don't attempt that yet [bruce 040923,
        # verified with Josh]
        change_desc = "your changes are"
        msg = "%s Cancel not implemented -- %s still there.\n\
        You can only leave this mode via Done." % \
              ( self.msg_commandName, change_desc )
        self.warning( msg, bother_user_with_dialog = 1)
        return True # refuse the Cancel
    
    def restore_gui(self):
        """
        Do changes to the GUI while exiting this mode. This includes closing 
        this mode's property manager, updating the command explorer , 
        disconnecting widget slots etc. 
        @see: L{self.init_gui}
        """
        self.w.toolsDepositAtomAction.setChecked(False)
        self.connect_or_disconnect_signals(False)
        self.enable_gui_actions(True)
        self.updateCommandToolbar(bool_entering = False)
        self.propMgr.close()
        
                                
# Now uses superclass method selectAtomsMode.restore_patches(). mark 060207.
# [not true anymore, evidently -- so what does it use? bruce 071011]
# [guessing it's more like restore_patches_by_GraphicsMode than _by_Command -- bruce 071012]
#    def restore_patches_by_GraphicsMode(self):
#        self.o.setDisplay(self.saveDisp) #bruce 041129; see notes for bug 133
#        self.o.selatom = None

    def clear(self):
        self.new = None

    # event methods
    
    def keyPress(self, key):
        for sym, code, num in elemKeyTab: # Set the atom type in the MMKit and combobox.
            if key == code:
                self.w.setElement(num) ###@@@ does this update our own spinbox too??
                ### REVIEW: should we add a 'return' here, to prevent the superclass
                # from taking more actions from the same keyPress?? [bruce question 071012]
        
        # Pressing Escape does the following:
        # 1. If a Bond Tool or the Atom Selection Filter is enabled, pressing Escape will activate the Atom Tool
        # and disable the Atom Selection Filter. The current selection remains unchanged, however.
        # 2. If the Atom Tool is enabled and the Atom Selection Filter is disabled, Escape will clear the 
        # current selection (when it's handled by our superclass's keyPress method).
        # Fixes bug (nfr) 1770. mark 060402
        if key == Qt.Key_Escape:
            if not self.depositAtomsAction.isChecked() or self.w.selection_filter_enabled:
                # Uncheck (disable) the Atom Selection Filter and activate the 
                # Atom Tool.
                if self.propMgr.selectionFilterCheckBox:
                    self.propMgr.selectionFilterCheckBox.setChecked(0) 
                self.depositAtomsAction.setChecked(1)
                return
        
        _superclass.keyPress(self, key)
        
        return
        
    def update_cursor_for_no_MB_selection_filter_disabled(self):
        """
        Update the cursor for 'Build' mode (when no mouse button is pressed).
        """
        
        cursor_id = 0
        if hasattr(self.w, "current_bondtool_button") and self.w.current_bondtool_button is not None:
            cursor_id = self.w.current_bondtool_button.index
        
        if self.depositAtomsAction.isChecked(): cursor_id =0
        elif self.bond1Action.isChecked(): cursor_id = 1
        elif self.bond2Action.isChecked(): cursor_id = 2
        elif self.bond3Action.isChecked(): cursor_id = 3
        elif self.bondaAction.isChecked(): cursor_id = 4
        elif self.bondgAction.isChecked(): cursor_id = 5
        elif self.cutBondsAction.isChecked(): cursor_id = 6
        else: cursor_id = 0      
        
        if self.o.modkeys is None:             
            self.o.setCursor(self.w.BondToolCursor[cursor_id])
        elif self.o.modkeys == 'Shift':
            self.o.setCursor(self.w.BondToolAddCursor[cursor_id])
        elif self.o.modkeys == 'Control':
            self.o.setCursor(self.w.BondToolSubtractCursor[cursor_id])
        elif self.o.modkeys == 'Shift+Control':
            self.o.setCursor(self.w.DeleteCursor)
        else:
            print "Error in update_cursor_for_no_MB(): Invalid modkey=", self.o.modkeys
        return

    def getCoords(self, event):
        """
        Retrieve the object coordinates of the point on the screen
        with window coordinates(int x, int y) 
        """
        # bruce 041207 comment: only called for depositMode leftDown in empty
        # space, to decide where to place a newly deposited chunk.
        # So it's a bit weird that it calls findpick at all!
        # In fact, the caller has already called a similar method indirectly
        # via update_selatom on the same event. BUT, that search for atoms might
        # have used a smaller radius than we do here, so this call of findpick
        # might sometimes cause the depth of a new chunk to be the same as an
        # existing atom instead of at the water surface. So I will leave it
        # alone for now, until I have a chance to review it with Josh [bug 269].
        # bruce 041214: it turns out it's intended, but only for atoms nearer
        # than the water! Awaiting another reply from Josh for details.
        # Until then, no changes and no reviews/bugfixes (eg for invisibles).
        # BTW this is now the only remaining call of findpick [still true 060316].
        # Best guess: this should ignore invisibles and be limited by water
        # and near clipping; but still use 2.0 radius. ###@@@

        # bruce 041214 comment: this looks like an inlined mousepoints...
        # but in fact [060316 addendum] it shares initial code with mousepoints,
        # but not all of mousepoints's code, so it makes sense to leave it as a
        # separate code snippet for now.
        x = event.pos().x()
        y = self.o.height - event.pos().y()

        p1 = A(gluUnProject(x, y, 0.0))
        p2 = A(gluUnProject(x, y, 1.0))

        at = self.o.assy.findpick(p1,norm(p2-p1),2.0)
        if at: pnt = at.posn()
        else: pnt = - self.o.pov
        k = (dot(self.o.lineOfSight,  pnt - p1) /
             dot(self.o.lineOfSight, p2 - p1))

        return p1+k*(p2-p1) # always return a point on the line from p1 to p2

    def pastable_element(self):
        if self.propMgr and hasattr(self.propMgr, 'elementChooser'):
            return self.propMgr.elementChooser.getElement()
        else:
            # we're presumably a subclass with no propMgr or a different one
            from elements import Carbon
            return Carbon

    _pastable_atomtype = None
    def set_pastable_atomtype(self, name):
        current_element = self.pastable_element()
        self._pastable_atomtype = current_element.find_atomtype(name)
            # store entire atomtype object; only used if element remains correct (not an error if it doesn't)
        return

    def pastable_atomtype(self):
        """
        Return the current pastable atomtype.

        [REVIEW: This appears to be very similar (if not completely redundant) to 
        get_atomtype_from_MMKit() in this file. This is still used as of 071025;
        that one is called only by the slot transmutePressed -- can that still
        be called?]
        """
        #e we might extend this to remember a current atomtype per element... not sure if useful
        current_element = self.pastable_element()
        if len(current_element.atomtypes) > 1:
            if self.propMgr and hasattr(self.propMgr, 'elementChooser'):
                try:
                    hybrid_name = self.propMgr.elementChooser.atomType                
                    atype = current_element.find_atomtype(hybrid_name)
                    if atype is not None:
                        self._pastable_atomtype = atype
                except:
                    print_compact_traceback("exception (ignored): ") # error, but continue
                pass
            else:
                # we're presumably a subclass with no propMgr or a different one
                pass
        if self._pastable_atomtype is not None and self._pastable_atomtype.element is current_element:
            return self._pastable_atomtype
        self._pastable_atomtype = current_element.atomtypes[0]
        return self._pastable_atomtype

    def ensure_visible(self, stuff, status):
        """
        If any chunk in stuff (a node, or a list of nodes) is not visible now, make it visible by changing its
        display mode, and append a warning about this to the given status message,
        which is returned whether or not it's modified.

        Suggested revision: if some chunks in a library part are explicitly invisible and some are visible, I suspect this
        behavior is wrong and it might be better to require only that some of them are visible,
        and/or to only do this when overall display mode was visible. [bruce 051227]

        Suggested revision: maybe the default display mode for deposited stuff should also be user-settable. [bruce 051227]
        """
        # By bruce 041207, to fix bug 229 part B (as called in comment #2),
        # by making each deposited chunk visible if it otherwise would not be.
        # Note that the chunk is now (usually?) the entire newly deposited thing,
        # but after future planned changes to the code, it might instead be a
        # preexisting chunk which was extended. Either way, we'll make the
        # entire chunk visible if it's not.
        #bruce 051227 revising this to handle more general deposited_stuff, for deposited library parts.
        n = self.ensure_visible_0( stuff)
        if n:
            status += " (warning: gave it Tubes display mode)"
            #k is "it" correct even for library parts? even when not all deposited chunks were changed?
        return status

    def ensure_visible_0(self, stuff): #bruce 051227 split out and generalized
        """
        [private recursive worker method for ensure_visible;
        returns number of things whose display mode was modified]
        """
        if not stuff:
            return 0 #k can this happen? I think so, since old code could handle it.
        if isinstance(stuff, Chunk):
            chunk = stuff
            if chunk.get_dispdef(self.o) == diINVISIBLE:
                chunk.setDisplay(diTUBES) # Build mode's own default display mode
                return 1
            return 0
        elif isinstance(stuff, Group):
            return self.ensure_visible_0( stuff.members)
        elif isinstance(stuff, type([])):
            res = 0
            for m in stuff:
                res += self.ensure_visible_0( m)
            return res
        else:
            assert isinstance(stuff, Node) # presumably Jig
            ##e not sure how to handle this or whether we need to [bruce 051227]; leave it out and await bug report?
            # [this will definitely occur once there's a partlib part which deposits a Jig or Comment or Named View;
            #  for Jigs should it Unhide them? For that matter, what about for Chunks? What if the hiddenness or
            #  invisibility came from the partlib?]
            if platform.atom_debug:
                print "atom_debug: ignoring object of unhandled type (Jig? Comment? Named View?) in ensure_visible_0", stuff
            return 0
        pass
    
    def __createBond(self, s1, a1, s2, a2):
        """
        Create bond between atom <a1> and atom <a2>, <s1> and <s2>
        are their singlets. No rotation/movement involved. Based on
        a method 'actually_bond()' in bonds.py--[Huaicai 8/25/05]
        """
        try: # use old code until new code works and unless new code is needed; CHANGE THIS SOON #####@@@@@
            v1, v2 = s1.singlet_v6(), s2.singlet_v6() # new code available
            assert v1 != V_SINGLE or v2 != V_SINGLE # new code needed
        except:
            # old code can be used for now
            s1.kill()
            s2.kill()
            bond_atoms(a1,a2)
            return
        
        vnew = min(v1,v2)
        bond = bond_atoms(a1,a2,vnew,s1,s2) # tell it the singlets to replace or reduce; let this do everything now, incl updates
        return
    
    def _depositLibraryPart(self, newPart, hotspotAtom, atom_or_pos): # probably by Huaicai; revised by bruce 051227, 060627, 070501
        """
        This method serves as an overloaded method, <atom_or_pos> is 
        the Singlet atom or the empty position that the new part <newPart>
        [which is an assy, at least sometimes] will be attached to or placed at.
        [If <atom_or_pos> is a singlet, <hotspotAtom> should be an atom in some chunk in <newPart>.]
        Currently, it doesn't consider group or jigs in the <newPart>. Not so sure if my attempt to copy a part into
        another assembly is all right. [It wasn't, so bruce 051227 revised it.]
        Copies all molecules in the <newPart>, change their assy attribute to current assembly, move them into <pos>.
        [bruce 051227 new feature:] return a list of new nodes created, and a message for history (currently almost a stub).
        [not sure if subrs ever print history messages... if they do we'd want to return those instead.]
        """
        attach2Bond = False
        stuff = [] # list of deposited nodes [bruce 051227 new feature]
        
        if isinstance(atom_or_pos, Atom):
            attch2Singlet = atom_or_pos
            if hotspotAtom and hotspotAtom.is_singlet() and attch2Singlet .is_singlet():
                newMol = hotspotAtom.molecule.copy(None) # [this can break interchunk bonds, thus it still has bug 2028]
                newMol.setAssy(self.o.assy) #bruce 051227 revised this
                hs = newMol.hotspot
                ha = hs.singlet_neighbor() # hotspot neighbor atom
                attch2Atom = attch2Singlet.singlet_neighbor() # attach to atom

                rotCenter = newMol.center
                rotOffset = Q(ha.posn()-hs.posn(), attch2Singlet.posn()-attch2Atom.posn())
                newMol.rot(rotOffset)
                
                moveOffset = attch2Singlet.posn() - hs.posn()
                newMol.move(moveOffset)
                
                self.__createBond(hs, ha, attch2Singlet, attch2Atom)
                
                self.o.assy.addmol(newMol)
                stuff.append(newMol)

                #e if there are other chunks in <newPart>, they are apparently copied below. [bruce 060627 comment]
                
            else: ## something is wrong, do nothing
                return stuff, "internal error"
            attach2Bond = True
        else:
            placedPos = atom_or_pos
            if hotspotAtom:
                hotspotAtomPos = hotspotAtom.posn()
                moveOffset = placedPos - hotspotAtomPos
            else:
                if newPart.molecules:
                    moveOffset = placedPos - newPart.molecules[0].center #e not the best choice of center [bruce 060627 comment]
        
        if attach2Bond: # Connect part to a bondpoint of an existing chunk
            for m in newPart.molecules:
              if not m is hotspotAtom.molecule: 
                newMol = m.copy(None) # [this can break interchunk bonds, thus it still has bug 2028]
                newMol.setAssy(self.o.assy) #bruce 051227 revised this
                
                ## Get each of all other chunks' center movement for the rotation around 'rotCenter'
                coff = rotOffset.rot(newMol.center - rotCenter)
                coff = rotCenter - newMol.center + coff 
                
                # The order of the following 2 statements doesn't matter
                newMol.rot(rotOffset)
                newMol.move(moveOffset + coff)
                
                self.o.assy.addmol(newMol)
                stuff.append(newMol)
        else: # Behaves like dropping a part anywhere you specify, independent of existing chunks.
            # copy all nodes in newPart (except those in clipboard items), regardless of node classes;
            # put it in a new Group if more than one thing [bruce 070501]
            # [TODO: this should be done in the cases above, too, but that's not yet implemented,
            #  and requires adding rot or pivot to the Node API and revising the rot-calling code above,
            #  and also reviewing the definition of the "hotspot of a Part" and maybe of a "depositable clipboard item".]
            assert newPart.tree.is_group()
            nodes = list(newPart.tree.members) # might be []
            assy = self.o.assy
            newnodes = copied_nodes_for_DND(nodes, autogroup_at_top = True, assy = assy)
                # Note: that calls name_autogrouped_nodes_for_clipboard internally, if it forms a Group,
                # but we ignore that and rename the new node differently below, whether or not it was
                # autogrouped. We could just as well do the autogrouping ourselves...
                # Note [bruce 070525]: it's better to call copied_nodes_for_DND here than copy_nodes_in_order,
                # even if we didn't need to autogroup. One reason is that if some node is not copied,
                # that's not necessarily an error, since we don't care about 1-1 orig-copy correspondence here.
            if not newnodes:
                if newnodes is None:
                    print "bug: newnodes should not be None; nodes was %r (saved in debug._bugnodes)" % (nodes,)
                        # TODO: This might be possible, for arbitrary partlib contents, just not for legitimate ones...
                        # but partlib will probably be (or is) user-expandable, so we should turn this into history message,
                        # not a bug print. But I'm not positive it's possible w/o a bug, so review first. ###FIX [bruce 070501 comment]
                    import debug
                    debug._bugnodes = nodes
                    newnodes = []
                msg = redmsg( "error: nothing to deposit in [%s]" % quote_html(str(newPart.name)) )
                return [], msg
            assert len(newnodes) == 1 # due to autogroup_at_top = True
            # but the remaining code works fine regardless of len(newnodes), in case we make autogroup a preference
            for newnode in newnodes:
                # Rename newnode based on the partlib name and a unique number.
                # It seems best to let the partlib mmp file contents (not just filename)
                # control the name used here, so use newPart.tree.name rather than just newPart.name.
                # (newPart.name is a complete file pathname; newPart.tree.name is usually its basename w/o extension.)
                basename = str(newPart.tree.name)
                if basename == 'Untitled':
                    # kluge, for the sake of 3 current partlib files, and files saved only once by users (due to NE1 bug in save)
                    dirjunk, base = os.path.split(newPart.name)
                    basename, extjunk = os.path.splitext(base)
                from constants import gensym
                newnode.name = gensym( basename + " " ) # name library part based on basename recorded in its mmp file's top node
                newnode.move(moveOffset) #k not sure this method is correctly implemented for measurement jigs, named views
                assy.addnode(newnode)
                stuff.append(newnode)
            pass
            
##            #bruce 060627 new code: fix bug 2028 (non-hotspot case only) about interchunk bonds being broken
##            nodes = newPart.molecules
##            newnodes = copied_nodes_for_DND(nodes)
##            if newnodes is None:
##                print "bug: newnodes should not be None; nodes was %r (saved in debug._bugnodes)" % (nodes,)
##                debug._bugnodes = nodes
##                newnodes = [] # kluge
##            for newMol in newnodes:
##                # some of the following probably only work for Chunks,
##                # though coding them for other nodes would not be hard
##                newMol.setAssy(self.o.assy)
##                newMol.move(moveOffset)
##                self.o.assy.addmol(newMol)
##                stuff.append(newMol)

##            # pre-060627 old code, breaks interchunk bonds since it copies chunks one at a time (bug 2028)
##            for m in nodes:
##                newMol = m.copy(None)
##                newMol.setAssy(self.o.assy) #bruce 051227 revised this
##                
##                newMol.move(moveOffset)
##                
##                self.o.assy.addmol(newMol)
##                stuff.append(newMol)
##            pass
        self.o.assy.update_parts() #bruce 051227 see if this fixes the atom_debug exception in checkparts
        
        msg = greenmsg("deposited library part: ") + " [" + quote_html(str(newPart.name)) + "]"  #ninad060924 fix bug 1164 
        
        return stuff, msg  ####@@@@ should revise this message (stub is by bruce 051227)

# == LMB event handling methods ====================================
        
    def leftDouble(self, event): # mark 060126.
        """
        Double click event handler for the left mouse button. 
        """
        self.ignore_next_leftUp_event = True # Fixes bug 1467. mark 060307.
        
        if self.cursor_over_when_LMB_pressed == 'Empty Space':
            if self.o.tripleClick: # Fixes bug 2568. mark 2007-10-21
                return
            if self.o.modkeys != 'Shift+Control': # Fixes bug 1503.  mark 060224.
                deposited_obj = self.deposit_from_MMKit(self.getCoords(event)) # does win_update().
                if deposited_obj:
                    self.set_cmdname('Deposit ' + deposited_obj)
            return
            
        _superclass.leftDouble(self, event)
        
        return

# == end of LMB event handler methods

    def MMKit_clipboard_part(self): #bruce 060412; implem is somewhat of a guess, based on the code of self.deposit_from_MMKit
        """
        If the MMKit is currently set to a clipboard item, return that item's Part, else return None.
        """
        if self.w.depositState != 'Clipboard':
            return None
        if not self.pastable:
            return None
        return self.pastable.part
    
    def transdepositPreviewedItem(self, singlet):
        """
        Trans-deposit the current object in the preview groupbox of the 
        property manager  on all singlets reachable through 
        any sequence of bonds to the singlet <singlet>.
        """
        
        if not singlet.is_singlet(): 
            return

        # bruce 060412: fix bug 1677 (though this fix's modularity should be improved;
        #  perhaps it would be better to detect this error in deposit_from_MMKit).
        # See also other comments dated today about separate fixes of some parts of that bug.
        mmkit_part = self.MMKit_clipboard_part() # a Part or None
        if mmkit_part and self.o.assy.part is mmkit_part:
            env.history.message(redmsg("Can't transdeposit the MMKit's current clipboard item onto itself."))
            return
        
        singlet_list = self.o.assy.getConnectedSinglets([singlet])
        
        modkeys = self.o.modkeys # save the modkeys state
        if self.o.modkeys is None and env.prefs[buildModeSelectAtomsOfDepositedObjEnabled_prefs_key]:
            # Needed when 'Select Atoms of Deposited Object' pref is enabled. mark 060314.
            self.o.modkeys = 'Shift'    
            self.o.assy.unpickall_in_GLPane() # [was unpickatoms; this (including Nodes) might be an undesirable change -- bruce 060721]
        
        self.transdepositing = True
        nobjs = 0
        ntried = 0 
        msg_deposited_obj = None
        for s in singlet_list: # singlet_list built in singletSetup() [not true; is that a bug?? bruce 060412 question]
            if not s.killed(): # takes care of self.obj_doubleclicked, too.
                deposited_obj = self.deposit_from_MMKit(s)
                ntried += 1
                if deposited_obj is not None:
                    #bruce 060412 -- fix part of bug 1677 -- wrong histmsg 'Nothing Transdeposited' and lack of mt_update
                    msg_deposited_obj = deposited_obj # I think these will all be the same, so we just use the last one
                    nobjs += 1
        self.transdepositing = False
        self.o.modkeys = modkeys # restore the modkeys state to real state.

        del deposited_obj
        
        if msg_deposited_obj is None: 
            # Let user know nothing was trandeposited. Fixes bug 1678. mark 060314.
            # (This was incorrect in bug 1677 since it assumed all deposited_obj return values were the same,
            #  but in that bug (as one of several problems in it) the first retval was not None but the last one was,
            #  so this caused a wrong message and a failure to update the MT. Fixed those parts of bug 1677
            #  by introducing msg_deposited_obj and using that here instead of deposited_obj. Fixed other parts of it
            #  in MMKit and elsewhere in this method. [bruce 060412])
            env.history.message('Nothing Transdeposited')
            return
            
        self.set_cmdname('Transdeposit ' + msg_deposited_obj)
        msg_deposited_obj += '(s)'
        
        info = fix_plurals( "%d %s deposited." % (nobjs, msg_deposited_obj) )
        if ntried > nobjs:
            # Note 1: this will be true in bug 1677 (until it's entirely fixed) [bruce 060412]
            # Note 2: this code was tested and worked, before I fully fixed bug 1677;
            # now that bug is fully fixed above (in the same commit as this code),
            # so this code is not known to ever run,
            # but I'll leave it in in case it mitigates any undiscovered bugs.
            info += " (%d not deposited due to a bug)" % (ntried - nobjs)
            info = orangemsg(info)
        env.history.message(info)
        self.w.win_update()

    def bond_type_changer_is_active(self): #bruce 060702 (modified from condition used in bondLeftUp)
        """
        Based on the present Build dashboard state (of bond type changing tools vs Atom tool),
        should clicks on bonds change their bond type? (used for click effect and highlight color)
        [overrides superclass method]
        """
        # Note: the intent of self.bondclick_v6 was to be true only when this should return true,
        # but the Atom tool does not yet conform to that,
        # and the existing code as of 060702 appears to use this condition,
        # so for now [bruce 060702] it's deemed the official condition.
        # But I can't tell for sure whether the other conditions (modkeys, or commented out access to another button)
        # belong here, so I didn't copy them here but left the code in bondLeftUp unchanged (at least for A8).
        
        # In A8, self.depositAtomsAction was self.w.depositAtomDashboard.buildBtn. Since the dashboard will be moved to 
            #Property Manager, gradually, all self.w.depositAtomDashboard calls will be changed to sel.MMKit calls. 
            #Also note that , it may even be called by a different name instead of MMKit (e.g. BuildPropertyManager which might
            #be called as self.propMgr.pw.blahblah where self.propMgr.pw = active part window. This comment is subjected to revision - Ninad 061214
        #ninad 070205: self.buildBtn is now replaced with self.depositAtomsAction
        return not self.depositAtomsAction.isChecked()
    
    
    def bondLeftUp(self, b, event): # was bondClicked(). mark 060220. [WARNING: docstring appears to be out of date -- bruce 060702]
        """
        Bond <b> was clicked, so select or unselect its atoms or delete bond <b> 
        based on the current modkey.
        - If no modkey is pressed, clear the selection and pick <b>\'s two atoms.
        - If Shift is pressed, pick <b>\'s two atoms, adding them to the current selection.
        - If Ctrl is pressed,  unpick <b>\'s two atoms, removing them from the current selection.
        - If Shift+Control (Delete) is pressed, delete bond <b>.
        <event> is a LMB release event.
        """

        if self.o.modkeys is None:
           
            if not self.depositAtomsAction.isChecked(): ### see also self.bond_type_changer_is_active()
            # In A8, self.depositAtomsAction was self.w.depositAtomDashboard.buildBtn. Since the dashboard will be moved to 
            #Property Manager, gradually, all self.w.depositAtomDashboard calls will be changed to sel.MMKit calls. 
            #Also note that , it may even be called by a different name instead of MMKit (e.g. BuildPropertyManager which might
            #be called as self.propMgr.pw.blahblah where self.propMgr.pw = active part window. This comment is subjected to revision - Ninad 061214
            
            #Following fixes bug 2425 (implements single click bond deletion 
            #in Build Atoms. -- ninad 20070626
                if self.cutBondsAction.isChecked():
                    self.bondDelete(event)
                    #@ self.o.gl_update() # Not necessary since win_update()
                                          # is called in bondDelete(). 
                                          # Mark 2007-10-19
                    return
                self.bond_change_type(b, allow_remake_bondpoints = True)
                self.o.gl_update()
                return
        
        _superclass.bondLeftUp(self, b, event)
            
    def bond_change_type(self, b, allow_remake_bondpoints = True): #bruce 050727; revised 060703
        """
        Change bondtype of bond <b> to new bondtype determined by the dashboard (if allowed).
        """
        # renamed from clicked_on_bond() mark 060204.
        v6 = self.bondclick_v6
        if v6 is not None:
            self.set_cmdname('Change Bond')
            btype = btype_from_v6( v6)
            from bond_utils import apply_btype_to_bond
            apply_btype_to_bond( btype, b, allow_remake_bondpoints = allow_remake_bondpoints)
                # checks whether btype is ok, and if so, new; emits history message; does [#e or should do] needed invals/updates
            ###k not sure if that subr does gl_update when needed... this method does it, but not sure how
            # [or maybe only its caller does?]
        return

# == Deposit methods

    def pickit(self):
        """
        Determines if the a deposited object (atom, clipboard node or library part) should have 
        its atoms automatically picked. Returns True or False based on the current modkey state.
        If modkey is None (no modkey is pressed), it will unpick all currently picked atoms.
        """
        if self.o.modkeys is None:
            self.o.assy.unpickall_in_GLPane() # [was unpickatoms; this is a guess, I didn't review the calls -- bruce 060721]
            if env.prefs[buildModeSelectAtomsOfDepositedObjEnabled_prefs_key]:
                # Added NFR 1504.  mark 060304.
                return True
            return False
        if self.o.modkeys == 'Shift':
            return True
        if self.o.modkeys == 'Control':
            return False
        else: # Delete
            return False
        
    def deposit_from_MMKit(self, atom_or_pos): #mark circa 051200; revised by bruce 051227
        """
        Deposit a new object based on the current selection in the MMKit/dashboard, 
        which is either an atom, a chunk on the clipboard, or a part from the library.
        If 'atom_or_pos' is a singlet, then it will bond the object to that singlet if it can.
        If 'atom_or_pos' is a position, then it will deposit the object at that coordinate.
        Return string <deposited_obj>, where:
            'Atoms' - an atom from the Atoms page was deposited.
            'Chunk' - a chunk from the Clipboard page was deposited.
            'Part' - a library part from the Library page was deposited.

        Note: this is overridden in some subclasses (e.g. PasteMode, PartLibraryMode),
        but the default implementation is also still used [as of 071025].
        """
        
        deposited_obj = None 
            #& deposited_obj is probably misnamed, since it is a string, not an object.  
            #& Would be nice if this could be an object. Problem is that clipboard and library
            #& both deposit chunks. mark 060314.
        
        if self.o.modkeys is None: # no Shift or Ctrl modifier key.
            self.o.assy.unpickall_in_GLPane() # Clear selection. [was unpickatoms -- bruce 060721]
        
        if self.w.depositState == 'Atoms':
            deposited_stuff, status = self.deposit_from_Atoms_page(atom_or_pos) # deposited_stuff is a chunk
            deposited_obj = 'Atom'
            
        elif self.w.depositState == 'Clipboard':
            deposited_stuff, status = self.deposit_from_Clipboard_page(atom_or_pos) # deposited_stuff is a chunk
            deposited_obj = 'Chunk'
                
        elif self.w.depositState == 'Library':
            #bruce 051227 revised this case and its subrs as part of fix of reopened bug 229;
            # deposited_stuff might be a chunk, node, list, etc.
            # Not sure if subrs still print redundant history messages besides the one
            # newly returned here (status).
            deposited_stuff, status = self.deposit_from_Library_page(atom_or_pos)
            deposited_obj = 'Part'
            if deposited_stuff and self.pickit():
                for d in deposited_stuff[:]:
                    d.pickatoms() # Fixes bug 1510. mark 060301.
            
        else:
            print_compact_stack('Invalid depositState = "' + str(self.w.depositState) + '" ')
            return
            
        self.o.selatom = None ##k could this be moved earlier, or does one of those submethods use it? [bruce 051227 question]
            
        # now fix bug 229 part B (as called in comment #2),
        # by making this new chunk (or perhaps multiple chunks, in deposited_stuff) visible if it otherwise would not be.
        # [bruce 051227 is extending this fix to depositing Library parts, whose initial implementation reinstated the bug.
        #  Note, Mark says the following comment is in 2 places but I can't find the other place, so not removing it yet.]
##        # We now have bug 229 again when we deposit a library part while in "invisible" display mode.
##        # Ninad is reopening bug 229 and assigning it to me.  This comment is in 2 places. Mark 051214.
##        if not library_part_deposited:  ##Added the condition [Huaicai 8/26/05] [bruce 051227 removed it, added a different one]

        if self.transdepositing:
            if not deposited_stuff:
                # Nothing was transdeposited.  Needed to fix bug 1678. mark 060314.
                return None
            return deposited_obj
        
        if deposited_stuff:
            self.w.win_update() 
                #& should we differentiate b/w win_update (when deposited_stuff is a new chunk added) vs. 
                #& gl_update (when deposited_stuff is added to existing chunk).  Discuss with Bruce. mark 060210.
            status = self.ensure_visible( deposited_stuff, status) #bruce 041207
            env.history.message(status)
        else:
            env.history.message(orangemsg(status)) # nothing deposited
        
        return deposited_obj
            
    def deposit_from_Library_page(self, atom_or_pos): 
        """
        Subclasses should override this method.
        """
        msg1= "Internal error:depositMode.deposit_from_Library_page should"
        msg2 = "be overridden"
        msg = msg1 + msg2
        return False, msg
        

    def deposit_from_Clipboard_page(self, atom_or_pos):
        """
        Deposits a copy of the selected object (chunk) from the MMKit Clipboard page, or
        the Clipboard (paste) combobox on the dashboard, which are the same object.
        If 'atom_or_pos' is a singlet, try bonding the object to the singlet by its hotspot.
        Otherwise, deposit the object at the position 'atom_or_pos'.
        Returns (chunk, status)
        """
        if isinstance(atom_or_pos, Atom):
            a = atom_or_pos
            if a.element is Singlet:
                if self.pastable: # bond clipboard object to the singlet
                    a0 = a.singlet_neighbor() # do this before <a> (the singlet) is killed
                    chunk, desc = self.pasteBond(a)
                    if chunk:
                        ## status = "replaced bondpoint on %r with %s (%s)" % (a0, chunk.name, desc)
                        status = "replaced bondpoint on %r with %s" % (a0, desc) # is this better? [bruce 050121]
                    else:
                        status = desc
                        # bruce 041123 added status message, to fix bug 163,
                        # and added the rest of them to describe what we do
                        # (or why we do nothing)
                else:
                    # Nothing selected from the Clipboard to paste, so do nothing
                    status = "nothing selected to paste" #k correct??
                    chunk = None #bruce 041207
        
        else:
            if self.pastable: # deposit into empty space at the cursor position
                chunk, desc = self.pasteFree(atom_or_pos)
                status = "pasted %s (%s) at %s" % (chunk.name, desc, self.posn_str(atom_or_pos))
            else:
                # Nothing selected from the Clipboard to paste, so do nothing
                status = "nothing selected to paste" #k correct??
                chunk = None #bruce 041207
        return chunk, status
        

    def deposit_from_Atoms_page(self, atom_or_pos):
        """
        Deposits an atom of the selected atom type from the MMKit Atoms page, or
        the Clipboard (atom and hybridtype) comboboxes on the dashboard, which are the same atom.
        If 'atom_or_pos' is a singlet, bond the atom to the singlet.
        Otherwise, set up the atom at position 'atom_or_pos' to be dragged around.
        Returns (chunk, status)
        """
        atype = self.pastable_atomtype() # Type of atom to deposit
        
        if isinstance(atom_or_pos, Atom):
            a = atom_or_pos
            if a.element is Singlet: # bond an atom of type atype to the singlet
                a0 = a.singlet_neighbor() # do this before <a> (the singlet) is killed!
                # (revised by bruce 050511)
                # if 1: # during devel, at least
                if platform.atom_debug: # Need this for A6 package builder to work.  Mark 050811.
                    import build_utils
                    reload(build_utils)
                from build_utils import AtomTypeDepositionTool
                deptool = AtomTypeDepositionTool( atype)
                if self.propMgr and hasattr(self.propMgr, 'autoBondCheckBox'):
                    autobond = self.propMgr.autoBondCheckBox.isChecked()
                else:
                    # we're presumably a subclass with no propMgr or a different one
                    autobond = True
                a1, desc = deptool.attach_to(a, autobond = autobond)
                        #e this might need to take over the generation of the following status msg...
                ## a1, desc = self.attach(el, a)
                if a1 is not None:
                    if self.pickit(): a1.pick()
                    #self.o.gl_update() #bruce 050510 moved this here from inside what's now deptool
                        # The only callers, deposit_from_MMKit() and transdepositPreviewedItem()
                        # are responsible for calling gl_update()/win_update(). mark 060314.
                    status = "replaced bondpoint on %r with new atom %s at %s" % (a0, desc, self.posn_str(a1))
                    chunk = a1.molecule #bruce 041207
                else:
                    status = desc
                    chunk = None #bruce 041207
                del a1, desc

        else: # Deposit atom at the cursor position and prep it for dragging
                cursorPos = atom_or_pos
                a = self.o.selatom = oneUnbonded(atype.element, self.o.assy, cursorPos, atomtype = atype)
                self.objectSetup(a)
                self.baggage, self.nonbaggage = a.baggage_and_other_neighbors()
                if self.pickit(): self.o.selatom.pick()
                status = "made new atom %r at %s" % (self.o.selatom, self.posn_str(self.o.selatom) )
                chunk = self.o.selatom.molecule #bruce 041207
        
        return chunk, status

    # == Singlet helper methods

    def singletLeftDown(self, s, event):
        if self.o.modkeys == 'Shift+Control':
            self.cursor_over_when_LMB_pressed = 'Empty Space'
            self.select_2d_region(event)
        else:
            self.cursor_over_when_LMB_pressed = 'Singlet'
            self.singletSetup(s)

    def singletSetup(self, a):
        """
        Setup for a click, double-click or drag event for singlet <a>.
        """
        self.objectSetup(a)
        self.only_highlight_singlets = True
        
        self.singlet_list = self.o.assy.getConnectedSinglets([a])
            # get list of all singlets that we can reach from any sequence of bonds to <a>.
            # used in doubleLeft() if the user clicks on

            # note: it appears that self.singlet_list is never used, tho another routine computes it
            # locally under the same name and uses that. [bruce 070411 comment, examining Qt3 branch]
        
        pivatom = a.neighbors()[0]
        self.baggage, self.nonbaggage = pivatom.baggage_and_other_neighbors() #bruce 051209
        neigh = self.nonbaggage

        self.baggage.remove(a) # always works since singlets are always baggage
        if neigh:
            if len(neigh)==2:
                self.pivot = pivatom.posn()
                self.pivax = norm(neigh[0].posn()-neigh[1].posn())
                self.baggage = [] #####@@@@@ revise nonbaggage too??
                #bruce suspects this might be a bug, looks like it prevents other singlets from moving, eg in -CX2- drag X
            elif len(neigh)>2:
                self.pivot = None
                self.pivax = None
                self.baggage = []#####@@@@@ revise nonbaggage too??
            else: # atom on a single stalk
                self.pivot = pivatom.posn()
                self.pivax = norm(self.pivot-neigh[0].posn())
        else: # no non-baggage neighbors
            self.pivot = pivatom.posn()
            self.pivax = None


    def singletDrag(self, bondpoint, event):
        """
        Drag a bondpoint.

        @param bondpoint: a bondpoint to drag
        @type bondpoint: some instances of class Atom
        
        @param event: a drag event
        """
        if bondpoint.element is not Singlet:
            return
         
        apos0 = bondpoint.posn()

        px = self.dragto_with_offset(bondpoint.posn(),
                                     event,
                                     self.drag_offset )
            #bruce 060316 attempt to fix bug 1474 analogue;
            # untested and incomplete since nothing is setting drag_offset
            # when this is called (except to its default value V(0,0,0))!
        
        if self.pivax:
            # continue pivoting around an axis
            quat = twistor(self.pivax,
                           bondpoint.posn() - self.pivot,
                           px - self.pivot)
            for at in [bondpoint] + self.baggage:
                at.setposn(quat.rot(at.posn() - self.pivot) + self.pivot)
        
        elif self.pivot:
            # continue pivoting around a point
            quat = Q(bondpoint.posn() - self.pivot, px - self.pivot)
            for at in [bondpoint] + self.baggage:
                at.setposn(quat.rot(at.posn() - self.pivot) + self.pivot)

        # highlight bondpoints we might bond this one to
        self.update_selatom(event, singOnly = True)

            #bruce 051209: to fix an old bug, don't call update_selatom
            # when dragging a real atom -- only call it here in this method,
            # when dragging a bondpoint. (Related: see warnings about
            # update_selatom's delayed effect, in its docstring or in leftDown.)
            # Q: when dragging a real atom, in some other method,
            # do we need to reset selatom instead?
            # [bruce 071025 rewrote that comment for its new context and for
            #  clarity, inferring meaning from other code & comments here;
            #  also rewrote the old comments below, in this method]
        
            #bruce 060726 question: why does trying singOnly = False here
            # have no visible effect? The only highlightings during drag
            # are the singlets, and real atoms that have singlets.
            # Where is the cause of this? I can't find any code resetting
            # selobj then. The code in update_selatom also looks like it
            # won't refrain from storing anything in selobj, based on
            # singOnly -- this only affects what it stores in selatom.
            # [later, 071025: wait, I thought it never stored anything in
            # selobj at all. Is its doc wrong, does it call update_selobj
            # and do that?]
            # Guesses about what code could be doing that (REVIEW):
            # selobj_still_ok? hicolor/selobj_highlight_color?
            # Also, note that not all drag methods call update_selobj at all.
            # (I think they then leave the old selobj highlighted --
            # dragging a real atom seems to do that.)
            #
            # My motivations for wanting to understand this: a need to let
            # self.drag_handler control what gets highlighted (and its color),
            # and unexplained behavior of testdraw.py after leftDown.

        # update the endpoints of the white rubberband line
        self.line = [bondpoint.posn(), px]
        
        apos1 = bondpoint.posn()
        if apos1 - apos0:
            msg = "pulling bondpoint %r to %s" % (bondpoint, self.posn_str(bondpoint))
            this_drag_id = (self.current_obj_start, self.__class__.leftDrag)
            env.history.message(msg, transient_id = this_drag_id)
            
        self.o.gl_update()
        return
        
    def singletLeftUp(self, s1, event):
        """
        Finish operation on singlet <s1> based on where the cursor is when the LMB was released:
        - If the cursor is still on <s1>, deposit an object from the MMKit on it
          [or as of 060702, use a bond type changing tool if one is active, to fix bug 833 item 1 ###implem unfinished?]
        - If the cursor is over a different singlet, bond <s1> to it.
        - If the cursor is over empty space, do nothing.
        <event> is a LMB release event.
        """
        self.line = None # required to erase white rubberband line on next gl_update. [bruce 070413 moved this before tests]

        if not s1.is_singlet():
            return

        if len(s1.bonds) != 1:
            return #bruce 070413 precaution

        neighbor = s1.singlet_neighbor()

        s2 = self.get_singlet_under_cursor(event, reaction_from = neighbor.element.symbol)
            # if reaction_from activates the atom under the cursor, s2 might be that atom itself, not a singlet,
            # or might be that atom after it transmutes itself into a singlet [bruce 070413 new feature]
            #
            ####@@@@ POSSIBLE BUG: s2 is not deterministic if cursor is over a real atom w/ >1 singlets (see its docstring);
            # this may lead to bond type changer on singlet sometimes but not always working, 
            # if cursor goes up over its base atom; or it may lead to nondeterministic remaining bondpoint
            # position or bondorder when bonding s1 to another atom.
            #   When it doesn't work (for bond type changer), it'll try to create a bond
            # between singlets on the same base atom; the code below indicates it won't really do it,
            # but may erroneously set_cmdname then (but if nothing changes this may not cause a bug in Undo menu text).
            # I tried to demo the basic bug (sometime-failure of bond type changer) but forgot to activate that tool.
            # But I found that debug prints and behavior make it look like something prevents highlighting s1's base atom,
            # but permits highlighting of other real atoms, during s1's drag. Even if that means this bug
            # can't happen, the code needs to be clarified. [bruce 060721 comment]
            
        if s2:
            if s2 is s1: # If the same singlet is highlighted...
                if self.bond_type_changer_is_active():
                    #bruce 060702 fix bug 833 item 1 (see also bondLeftUp)
                    b = s1.bonds[0]
                    self.bond_change_type(b, allow_remake_bondpoints = False) # does set_cmdname
                    self.o.gl_update() # (probably good for highlighting, even if bond_change_type refused)
                        # REVIEW (possible optim): can we use gl_update_highlight when only highlighting was changed? [bruce 070626]
                else:
                    # ...deposit an object (atom, chunk or library part) from MMKit on the singlet <s1>.
                    if self.mouse_within_stickiness_limit(event, DRAG_STICKINESS_LIMIT): # Fixes bug 1448. mark 060301.
                        deposited_obj = self.deposit_from_MMKit(s1)
                            # does its own win_update().
                        if deposited_obj:
                            self.set_cmdname('Deposit ' + deposited_obj)
            else: # A different singlet is highlighted...
                # If the singlets s1 & s2 are 3' and 5' or 5' and 3' bondpoints
                # of DNA strands, merge their strand chunks...
                open_bond1 = s1.bonds[0]
                open_bond2 = s2.bonds[0]
                
                # Cannot DND 3' open bonds onto 3' open bonds.  
                if open_bond1.isThreePrimeOpenBond() and \
                   open_bond2.isThreePrimeOpenBond():
                    msg = redmsg("Cannot join strands on 3' ends.")
                    self.propMgr.updateMessage(msg)
                    return
                # Cannot DND 5' open bonds onto 5' open bonds. 
                if open_bond1.isFivePrimeOpenBond() and \
                   open_bond2.isFivePrimeOpenBond():
                    msg = redmsg("Cannot join strands on 5' ends.")
                    self.propMgr.updateMessage(msg) 
                    return
                # Ok to DND 3' onto 5' or 5' onto 3'.
                if (open_bond1.isThreePrimeOpenBond() and \
                    open_bond2.isFivePrimeOpenBond()) or \
                   (open_bond1.isFivePrimeOpenBond()  and \
                    open_bond2.isThreePrimeOpenBond()):
                    a1 = open_bond1.other(s1)
                    a2 = open_bond2.other(s2)
                    # We rely on merge() to check that mols are not the same.
                    # merge also results in making the strand colors the same.
                    a1.molecule.merge(a2.molecule) 
                
                # ... now bond the highlighted singlet <s2> to the first singlet <s1>
                self.bond_singlets(s1, s2)
                self.set_cmdname('Create Bond')
                self.o.gl_update()
                self.propMgr.updateMessage() 
        else: # cursor on empty space
            self.o.gl_update() # get rid of white rubber band line.
            # REVIEW (possible optim): can we make gl_update_highlight cover this? [bruce 070626]
            
        self.only_highlight_singlets = False
        
    def get_singlet_under_cursor(self, event, reaction_from = None ):
        """
        If the object under the cursor is a singlet, return it.  If the object under the cursor is a
        real atom with one or more singlets, return one of its singlets. Otherwise, return None.
        """
        a = self.get_obj_under_cursor(event)
        if isinstance(a, Atom):
            if a.is_singlet():
                return a
            # Update, bruce 071121, about returning singlets bonded to real
            # atoms under the cursor, but not themselves under it:
            # Note that this method affects what happens
            # on leftup, but is not used to determine what gets highlighted
            # during mouse motion. A comment below mentions that
            # selobj_highlight_color is related to that. It looks like it has
            # code for this in selectAtomsMode._getAtomHighlightColor.
            # There is also a call
            # to update_selatom with singOnly = True, which doesn't have this
            # special case for non-bondpoints, but I don't know whether it's
            # related to what happens here. And finally, the element symbols
            # hardcoded below are no longer correct, so that Pl-Sh special case
            # is effectively disabled!
            # (Obsolete element symbols also appear elsewhere in *Mode.py.)
            # All this may or may not relate to bug 2587.
            if a.singNeighbors():
                if env.debug() and len(a.singNeighbors()) > 1:
                    #bruce 060721, cond revised 071121
                    print "debug warning (likely bug): get_singlet_under_cursor returning an arbitrary bondpoint of %r" % (a,)
                return a.singNeighbors()[0]
            if reaction_from == 'Pl' and a.element.symbol == 'Sh' and len(a.bonds) == 1 and len(a.realNeighbors()) == 1:
                #bruce 070413 for "Joining strands by dragging a Pl bondboint and dropping on Sh."
                # (Should also verify the realNeighbor is an Ss, I suppose... ##e)
                # Doing this here is not enough to make it work -- selectAtomsMode.selobj_highlight_color
                # filters the highlighting, and also needs to know this is ok, so I taught it (too generously, for now).
                # That's a kluge -- we need a central source for this info.
                if env.debug():
                    print "reacting Pl-bondpoint to %r, by transmuting %r to a bondpoint" % (a,a)
                a.mvElement(Singlet) ##e ok, but emits debug print -- should fix that.
                return a
        return None

    def bond_singlets(self, s1, s2):
        """
        Bond singlets <s1> and <s2> unless they are the same singlet.
        """
        #bruce 050429: it'd be nice to highlight the involved bonds and atoms, too...
        # incl any existing bond between same atoms. (by overdraw, for speed, or by more lines) ####@@@@ tryit
        #bruce 041119 split this out and added checks to fix bugs #203
        # (for bonding atom to itself) and #121 (atoms already bonded).
        # I fixed 121 by doing nothing to already-bonded atoms, but in
        # the future we might want to make a double bond. #e
        if s1.singlet_neighbor() is s2.singlet_neighbor():
            # this is a bug according to the subroutine [i.e. bond_at_singlets, i later guess], but not to us
            print_error_details = 0
        else:
            # for any other error, let subr print a bug report,
            # since we think we caught them all before calling it
            print_error_details = 1
        flag, status = bond_at_singlets(s1, s2, move = False, \
                         print_error_details = print_error_details, increase_bond_order = True)

        # we ignore flag, which says whether it's ok, warning, or error
        env.history.message("%s: %s" % (self.msg_commandName, status))
        return


    ###################################################################
    #==   Cutting and pasting
    ###################################################################
    
    def pasteBond(self, sing):
        """
        If self.pastable has an unambiguous hotspot,
        paste a copy of self.pastable onto the given singlet;
        return (the copy, description) or (None, whynot)
        """
        self.update_pastable()
        pastable = self.pastable
            # as of 050316 addmol can change self.pastable! See comments in pasteFree.
        # bruce 041123 added return values (and guessed docstring).
        # bruce 050121 using subr split out from this code
        ok, hotspot_or_whynot = find_hotspot_for_pasting(pastable)
        if not ok:
            whynot = hotspot_or_whynot
            return None, whynot
        
        hotspot = hotspot_or_whynot
        
        if isinstance(pastable, Chunk):
            numol = pastable.copy(None)
            # bruce 041116 added (implicitly, by default) cauterize = 1
            # to mol.copy() above; change this to cauterize = 0 here if unwanted,
            # and for other uses of mol.copy in this file.
            # For this use, there's an issue that new singlets make it harder to
            # find a default hotspot! Hmm... I think copy should set one then.
            # So now it does [041123].
            hs = numol.hotspot or numol.singlets[0] #e should use find_hotspot_for_pasting again
            bond_at_singlets(hs,sing) # this will move hs.molecule (numol) to match
            # bruce 050217 comment: hs is now an invalid hotspot for numol, and that
            # used to cause bug 312, but this is now fixed in getattr every time the
            # hotspot is retrieved (since it can become invalid in many other ways too),
            # so there's no need to explicitly forget it here.
            if self.pickit():
                numol.pickatoms()
                #bruce 060412 worries whether pickatoms is illegal or ineffective (in both pasteBond and pasteFree)
                # given that numol.part is presumably not yet set (until after addmol). But these seem to work
                # (assuming I'm testing them properly), so I'm not changing this. [Why do they work?? ###@@@]
            self.o.assy.addmol(numol) # do this last, in case it computes bbox
            return numol, "copy of %r" % pastable.name
        elif isinstance(pastable, Group):
            msg1 = "Pasting a group with hotspot onto a bond point "
            msg2 = "is not implemented"
            msg3  = msg1 + msg2 
            return None, msg3
            if platform.atom_debug:     
                #@@@ EXPERIMENTAL CODE TO PASTE a GROUP WITH A HOTSPOT  
                if 0:
                     # hotspot neighbor atom
                    attch2Singlet = atom_or_pos
                    hotspot_neighbor = hotspot.singlet_neighbor()
                    # attach to atom
                    attch2Atom = attch2Singlet.singlet_neighbor() 
                    rotOffset = Q(hotspot_neighbor.posn() - hotspot.posn(), 
                                  attch2Singlet.posn() - attch2Atom.posn())
                    
                    rotCenter = newMol.center
                    newMol.rot(rotOffset)
                    
                    moveOffset = attch2Singlet.posn() - hs.posn()
                    newMol.move(moveOffset)
                    
                    self.__createBond(hotspot, 
                                      hotspot_neighbor, 
                                      attch2Singlet, 
                                      attch2Atom)
                    self.o.assy.addmol(newMol)
                    ########
                    ##newGroup = self.pasteGroup(pos, pastable)      
                    return newGroup, "copy of %r" % newGroup.name
                
                    
        
    # paste the pastable object where the cursor is (at pos)
    # warning: some of the following comment is obsolete (read all of it for the details)
    # ###@@@ should clean up this comment and code
    # - bruce 041206 fix bug 222 by recentering it now --
    # in fact, even better, if there's a hotspot, put that at pos.
    # - bruce 050121 fixing bug in feature of putting hotspot on water
    # rather than center. I was going to remove it, since Ninad disliked it
    # and I can see problematic aspects of it; but I saw that it had a bug
    # of picking the "first singlet" if there were several (and no hotspot),
    # so I'll fix that bug first, and also call fix_bad_hotspot to work
    # around invalid hotspots if those can occur. If the feature still seems
    # objectionable after this, it can be removed (or made a nondefault preference).
    # ... bruce 050124: that feature bothers me, decided to remove it completely.
    def pasteFree(self, pos):
        self.update_pastable()
        pastable = self.pastable
            # as of 050316 addmol can change self.pastable!
            # (if we're operating in the same clipboard item it's stored in,
            #  and if adding numol makes that item no longer pastable.)
            # And someday the copy operation itself might auto-addmol, for some reason;
            # so to be safe, save pastable here before we change current part at all.
        
        chunk, status = self.o.assy.paste(pastable, pos)
        return chunk, status
  
    ## dashboard things

    def update_pastable(self): 
        """
        Subclasses should override this method. 
        @see: L{PasteMode.update_pastable} 
        """
        self.pastable = None        
        return
    
    def setPaste(self): #bruce 050121 heavily revised this
        """
        called from button presses and spinbox changes
        """
        self.update_pastable()
        if 1:
            ###@@@ always do this, since old code did this
            # and I didn't yet analyze changing cond to self.pastable
            self.w.depositState = 'Clipboard'
        else:
            pass
            ###@@@ should we do the opposite of the above when not self.pastable?
            # (or if it's no longer pastable?) guess: no.
        self.UpdateDashboard() #bruce 050121 added this
        return
        
##        if self.o.assy.shelf.members:
##            try:
##                ## bruce 050110 guessing this should be [cx] again:
##                ## self.pastable = self.o.assy.shelf.members[-1-cx]
##                self.pastable = self.o.assy.shelf.members[cx]
##                # bruce 041124 - changed [cx] to [-1-cx] (should just fix model tree)
##                # bruce 041124: the following status bar message (by me)
##                # is a good idea, but first we need to figure out how to
##                # remove it from the statusbar when it's no longer
##                # accurate!
##                #
##                ## env.history.message("Ready to paste %r" % self.pastable.name)
##            except: # IndexError (or its name is messed up)
##                # should never happen, but be robust [bruce 041124]
##                self.pastable = None
##        else:
##            self.pastable = None # bruce 041124

##        # bruce 041124 adding more -- I think it's needed to fully fix bug 169:
##        # update clipboard selection status to match the spinbox,
##        # but prevent it from recursing into our spinbox updater
##        self.dont_update_gui = True
##        try:
##            self.o.assy.shelf.unpick()
##            if self.pastable:
##                self.pastable.pick()
##        finally:
##            self.dont_update_gui = False
##            self.o.assy.mt.mt_update() # update model tree
##        return
        
    def setAtom(self):
        "Slot for Atoms Tool button in the Build Chunks property manager"
        self.pastable = None
        # but spinbox records it... but not if set of pastables is updated! so maybe a bad idea? ##k
        self.update_cursor()
        self.w.depositState = 'Atoms'
        self.UpdateDashboard() #bruce 050121 added this

    bondclick_v6 = None
    
    def changeBondTool(self, action):
        """
        Change the bond tool (e.g. single, double, triple, aromatic 
        and graphitic) depending upon the checked action.
        @param: action is the checked bond tool action in the 
        bondToolsActionGroup
        """
        state = action.isChecked()
        if action ==  self.bond1Action:
            self.setBond1(state)
        elif action == self.bond2Action:
            self.setBond2(state)
        elif action == self.bond3Action:
            self.setBond3(state)
        elif action == self.bondaAction:
            self.setBonda(state)
        elif action == self.bondgAction:
            self.setBondg(state)
        elif action == self.cutBondsAction:
            self.update_cursor()
            self.propMgr.updateMessage()
            
    def setBond1(self, state):
        "Slot for Bond Tool Single button."
        self.setBond(V_SINGLE, state)
        
    def setBond2(self, state):
        "Slot for Bond Tool Double button."
        self.setBond(V_DOUBLE, state)
    
    def setBond3(self, state):
        "Slot for Bond Tool Triple button."
        self.setBond(V_TRIPLE, state )
        
    def setBonda(self, state):
        "Slot for Bond Tool Aromatic button."
        self.setBond(V_AROMATIC, state)

    def setBondg(self, state): #mark 050831
        "Slot for Bond Tool Graphitic button."
        self.setBond(V_GRAPHITE, state)
        
    def setBond(self, v6, state, button = None):
        """
        #doc; v6 might be None, I guess, though this is not yet used
        """
        if state:
            if self.bondclick_v6 == v6 and button is not None and v6 is not None:
                # turn it off when clicked twice -- BUG: this never happens, maybe due to QButtonGroup.setExclusive behavior
                self.bondclick_v6 = None
                button.setChecked(False) # doesn't work?
            else:
                self.bondclick_v6 = v6
            if self.bondclick_v6:
                name = btype_from_v6(self.bondclick_v6)
                env.history.statusbar_msg("click bonds to make them %s" % name) # name is 'single' etc
                self.propMgr.updateMessage() # Mark 2007-06-01
            else:
                # this never happens (as explained above)
                #####@@@@@ see also setAtom, which runs when Atom Tool is clicked (ideally this might run as well, but it doesn't)
                # (I'm guessing that self.bondclick_v6 is not relied on for action effects -- maybe the button states are??)
                # [bruce 060702 comment]
                env.history.statusbar_msg(" ") # clicking bonds now does nothing
                ## print "turned it off"
        else:
            pass # print "toggled(false) for",btype_from_v6(v6) # happens for the one that was just on, unless you click same one
        self.update_cursor()
        
        return
        
    def setWater(self, on):
        """
        Turn water surface on/off.
        if <on> is True, only atoms and bonds above the water surface can be highlighted and selected.
        if <on> is False, all atoms and bonds can be highlighted and selected, and the water surface is not displayed.
        """
        if on:
            self.water_enabled = True
            msg = "Water surface enabled."
        else:
            self.water_enabled = False
            msg = "Water surface disabled."
        env.history.message(msg)
        self.o.gl_update() # REVIEW (possible optim): can we make gl_update_highlight cover this? [bruce 070626]
        

    #== Transmute helper methods
    
    def get_atomtype_from_MMKit(self):
        """
        Return the current atomtype selected in the MMKit.
        
        Note: This appears to be very similar (if not completely redundant) to 
        pastable_atomtype() in this file. 
        """
        elm = self.propMgr.elementChooser.getElement()
        atomtype = None
        if len(elm.atomtypes) > 1: 
            try:
                # Obtain the hybrid index from the hybrid button group, not
                # the obsolete hybrid combobox. Fixes bug 2304. Mark 2007-06-20
                hybrid_name = self.propMgr.elementChooser.atomType
                atype = elm.find_atomtype(hybrid_name)
                if atype is not None:
                    atomtype = atype
            except:
                print_compact_traceback("exception (ignored): ") # error, but continue
            pass
        if atomtype is not None and atomtype.element is elm:
            return atomtype
            
        # For element that doesn't support hybridization
        return elm.atomtypes[0]
        
    def transmutePressed(self):
        """
        Slot for "Transmute" button.
        """
        force = env.prefs[keepBondsDuringTransmute_prefs_key]
        atomType = self.get_atomtype_from_MMKit()
        self.w.assy.modifyTransmute(self.propMgr.elementChooser.getElementNumber(), 
                                    force = force, 
                                    atomType=atomType)
        
    #== Draw methods
    
    def Draw(self):
        _superclass.Draw(self) # this includes self.o.assy.draw(self.o) [bruce 060724 comment]
        if self.line:
            color = get_selCurve_color(0,self.o.backgroundColor) 
                # Make sure line color has good contrast with bg. mark 060305.
            drawline(color, self.line[0], self.line[1])
            ####@@@@ if this is for a higher-order bond, draw differently
        ## self.o.assy.draw(self.o) # THIS WAS REDUNDANT [bruce 060724 removed it as a speedup]
        #bruce 050610 moved self.surface() call elsewhere [it's in Draw_after_highlighting]
        return

    def Draw_after_highlighting(self, pickCheckOnly=False): #bruce 050610
        # added pickCheckOnly arg.  mark 060207.
        """
        Do more drawing, after the main drawing code has completed its highlighting/stenciling for selobj.
        Caller will leave glstate in standard form for Draw. Implems are free to turn off depth buffer read or write.
        Warning: anything implems do to depth or stencil buffers will affect the standard selobj-check in bareMotion.
        [New method in mode API as of bruce 050610. General form not yet defined -- just a hack for Build mode's
         water surface. Could be used for transparent drawing in general.]
        """
        _superclass.Draw_after_highlighting(self, pickCheckOnly) #Draw possible other translucent objects. [huaicai 9/28/05]
        
        glDepthMask(GL_FALSE)
            # disable writing the depth buffer, so bareMotion selobj check measures depths behind it,
            # so it can more reliably compare them to water's constant depth. (This way, roundoff errors
            # only matter where the model hits the water surface, rather than over all the visible
            # water surface.)
            # (Note: before bruce 050608, depth buffer remained writable here -- untypical for transparent drawing,
            #  but ok then, since water was drawn last and bareMotion had no depth-buffer pixel check.)
        self.surface() 
        glDepthMask(GL_TRUE)
        return
        
    def surface(self):
        """
        Draw the water's surface -- a sketch plane to indicate where the new atoms will sit by default,
        which also prevents (some kinds of) selection of objects behind it.
        """
        if not self.water_enabled:
            return
            
        glDisable(GL_LIGHTING)
        glColor4fv(self.gridColor + (0.6,))
            ##e bruce 050615 comment: if this equalled bgcolor, some bugs would go away;
            # we'd still want to correct the surface-size to properly fit the window (bug 264, just now fixed below),
            # but the flicker to bgcolor bug (bug number?) would be gone (defined and effective bgcolor would be same).
            # And that would make sense in principle, too -- the water surface would be like a finite amount of fog,
            # concentrated into a single plane.
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # the grid is in eyespace
        glPushMatrix()
        q = self.o.quat
        glTranslatef(-self.o.pov[0], -self.o.pov[1], -self.o.pov[2])
        glRotatef(- q.angle*180.0/math.pi, q.x, q.y, q.z)

##        # The following is wrong for wide windows (bug 264).
##      # To fix it requires looking at how scale is set (differently
##      # and perhaps wrongly (related to bug 239) for tall windows),
##      # so I'll do it later, after fixing bug 239.
##      # Warning: correctness of use of x vs y below has not been verified.
##      # [bruce 041214] ###@@@
##      # ... but for Alpha let's just do a quick fix by replacing 1.5 by 4.0.
##      # This should work except for very wide (or tall??) windows.
##      # [bruce 050120]
##      
##        ## x = y = 4.0 * self.o.scale # was 1.5 before bruce 050120; still a kluge
        
        #bruce 050615 to fix bug 264 (finally! but it will only last until someone changes what self.o.scale means...):
        # here are presumably correct values for the screen boundaries in this "plane of center of view":
        y = self.o.scale # always fits height, regardless of aspect ratio (as of 050615 anyway)
        x = y * (self.o.width + 0.0) / self.o.height
        # (#e Ideally these would be glpane attrs so we wouldn't have to know how to compute them here.)
        # By test, these seem exactly right (tested as above and after x,y *= 0.95),
        # but for robustness (in case of roundoff errors restoring eyespace matrices)
        # I'll add an arbitrary fudge factor (both small and overkill at the same time!):
        x *= 1.1
        y *= 1.1
        x += 5
        y += 5
        glBegin(GL_QUADS)
        glVertex(-x,-y,0)
        glVertex(x,-y,0)
        glVertex(x,y,0)
        glVertex(-x,y,0)
        glEnd()
        glPopMatrix()
        glDisable(GL_BLEND)
        glEnable(GL_LIGHTING)
        return

    def viewing_main_part(self): #bruce 050416 ###e should refile into assy
        return self.o.assy.current_selgroup_iff_valid() is self.o.assy.tree
        
    def makeMenus(self): #bruce 050705 revised this to support bond menus
        "#doc"
        selatom, selobj = self.update_selatom_and_selobj( None)
            # bruce 050612 added this [as an update_selatom call] -- not needed before since bareMotion did it (I guess).
            # [replaced with update_selatom_and_selobj, bruce 050705]
        
        self.Menu_spec = []
        ###e could include disabled chunk & selatom name at the top, whether selatom is singlet, hotspot, etc.
        
        # figure out which Set Hotspot menu item to include, and whether to disable it or leave it out
        if self.viewing_main_part():
            text, meth = ('Set Hotspot and Copy', self.setHotSpot_mainPart)
                # bruce 050121 renamed this from "Set Hotspot" to "Set Hotspot and Copy as Pastable".
                # bruce 050511 shortened that to "Set Hotspot and Copy".
                # If you want the name to be shorter, then change the method
                # to do something simpler! Note that the locally set hotspot
                # matters if we later drag this chunk to the clipboard.
                # IMHO, the complexity is a sign that the design
                # should not yet be considered finished!
        else:
            text, meth = ('Set Hotspot of clipboard item', self.setHotSpot_clipitem)
                ###e could check if it has a hotspot already, if that one is different, etc
                ###e could include atom name in menu text... Set Hotspot to X13
        if selatom is not None and selatom.is_singlet():
            item = (text, meth)
        elif selatom is not None:
            item = (text, meth, 'disabled')
        else:
            item = None
        if item:
            self.Menu_spec.append(item)
        
        # Add the trans-deposit menu item.
        if selatom is not None and selatom.is_singlet():
            self.Menu_spec.append(( 'Trans-deposit previewed item', lambda dragatom=selatom: self.transdepositPreviewedItem(dragatom) ))

        # figure out Select This Chunk item text and whether to include it
        ##e (should we include it for internal bonds, too? not for now, maybe not ever. [bruce 050705])
        if selatom is not None:
            name = selatom.molecule.name
            item = ('Select Chunk %r' % name, self.select)
                # bruce 050121 changed Select to a more explicit name, Select This Chunk.
                # bruce 050416 using actual chunk name. (#e Should we worry about it being too long?)
                #e should rename self.select method, once I'm sure it's not called elsewhere (not easy to confirm)
                #e maybe should disable this or change to checkmark item (with unselect action) if it's already selected??
            self.Menu_spec.append(item)

        ##e add something similar for bonds, displaying their atoms, and the bonded chunk or chunks?

        if selatom is not None:
            is_singlet = selatom.is_singlet() and len(selatom.bonds) == 1 #k is 2nd cond redundant with is_singlet()?
        else:
            is_singlet = False

        # add submenu to change atom hybridization type [initial kluge]
        atomtypes = (selatom is None) and ['fake'] or selatom.element.atomtypes
            # kluge: ['fake'] is so the idiom "x and y or z" can pick y;
            # otherwise we'd use [] for 'y', but that doesn't work since it's false.
##        if selatom is not None and not selatom.is_singlet():
##            self.Menu_spec.append(( '%s' % selatom.atomtype.fullname_for_msg(), noop, 'disabled' )) 
        if len(atomtypes) > 1: # i.e. if elt has >1 atom type available! (then it must not be Singlet, btw)
            # make a submenu for the available types, checkmarking the current one, disabling if illegal to change, sbartext for why
            # (this code belongs in some more modular place... where exactly? it's part of an atom-type-editor for use in a menu...
            #  put it with Atom, or with AtomType? ###e)
            submenu = []
            for atype in atomtypes:
                submenu.append(( atype.fullname_for_msg(), lambda arg1=None, arg2=None, atype=atype: atype.apply_to(selatom),
                                 # Notes: the atype=atype is required -- otherwise each lambda refers to the same
                                 # localvar 'atype' -- effectively by reference, not by value --
                                 # even though it changes during this loop!
                                 #   Also at least one of the arg1 and arg2 are required, otherwise atype ends up being an int,
                                 # at least acc'd to exception we get here. Why is Qt passing this an int? Nevermind for now. ###k
                             (atype is selatom.atomtype) and 'checked' or None,
                             (not atype.ok_to_apply_to(selatom)) and 'disabled' or None
                           ))
            self.Menu_spec.append(( 'Atom Type: %s' % selatom.atomtype.fullname_for_msg(), submenu ))
##            self.Menu_spec.append(( 'Atom Type', submenu ))

        ###e offer to change element, too (or should the same submenu be used, with a separator? not sure)

        # for a highlighted bond, add submenu to change bond type, if atomtypes would permit that;
        # or a menu item to just display the type, if not. Also add summary info about the bond...
        # all this is returned (as a menu_spec sublist) by one external helper method.
        
        if is_singlet:
            selbond = selatom.bonds[0]
        else:
            selbond = selobj # might not be a Bond (could be an Atom or None)
        
        try:
            method = selbond.bond_menu_section
        except AttributeError:
            # selbond is not a Bond
            pass
        else:
            glpane = self.o
            quat = glpane.quat
            try:
                menu_spec = method(quat = quat) #e pass some options??
            except:
                print_compact_traceback("exception in bond_menu_section for %r, ignored: " % (selobj,))
            else:
                if menu_spec:
                    self.Menu_spec.extend(menu_spec)
                pass
            pass

        # Local minimize [now called Adjust Atoms in history/Undo, Adjust <what> here and in selectMode -- mark & bruce 060705]
        # WARNING: This code is duplicated in selectMode.makeMenus(). mark 060314.
        if selatom is not None and not selatom.is_singlet() and self.w.simSetupAction.isEnabled():
            # if simSetupAction is not enabled, a sim process is running.  Fixes bug 1283. mark 060314.
            ## self.Menu_spec.append(( 'Adjust atom %s' % selatom, selatom.minimize_1_atom )) # older pseudocode
            # experimental. if we leave in these options, some of them might want a submenu.
            # or maybe the layer depth is a dashboard control? or have buttons instead of menu items?
            self.Menu_spec.append(( 'Adjust atom %s' % selatom, lambda e1=None,a=selatom: self.localmin(a,0) ))
            self.Menu_spec.append(( 'Adjust 1 layer', lambda e1=None,a=selatom: self.localmin(a,1) ))
            self.Menu_spec.append(( 'Adjust 2 layers', lambda e1=None,a=selatom: self.localmin(a,2) ))
        
        # offer to clean up singlet positions (not sure if this item should be so prominent)
        if selatom is not None and not selatom.is_singlet():
            sings = selatom.singNeighbors() #e when possible, use baggageNeighbors() here and remake_baggage below. [bruce 051209]
            if sings or selatom.bad():
                if sings:
                    text = 'Reposition bondpoints'
                        # - this might be offered even if they don't need repositioning;
                        # not easy to fix, but someday we'll always reposition them whenever needed
                        # and this menu command can be removed then.
                        # - ideally we'd reposition H's too (i.e. call remake_baggage below)
                else:
                    text = 'Add bondpoints' # this text is only used if it doesn't have enough
                self.Menu_spec.append(( text, selatom.remake_bondpoints )) #e should finish and use remake_baggage (and baggageNeighbors)
        
        # selobj-specific menu items.  This is duplicated in selectMode.makeMenus().
        # [bruce 060405 added try/except, and generalized this from Jig-specific to selobj-specific items,
        #  by replacing isinstance(selobj, Jig) with hasattr(selobj, 'make_selobj_cmenu_items'),
        #  so any kind of selobj can provide more menu items using this API.
        #  Note that the only way selobj could customize its menu items to the calling command or its graphicsMode
        #  would be by assuming that was the currentCommand or its graphicsMode. Someday we might extend the API
        #  to pass it glpane, so we can support multiple glpanes, each in a different command and/or graphicsMode. #e]
        if selobj is not None and hasattr(selobj, 'make_selobj_cmenu_items'):
            try:
                selobj.make_selobj_cmenu_items(self.Menu_spec)
            except:
                print_compact_traceback("bug: exception (ignored) in make_selobj_cmenu_items for %r: " % selobj)
        
        # separator and other mode menu items.
        if self.Menu_spec:
            self.Menu_spec.append(None)
            
        # Enable/Disable Jig Selection.  
        # This is duplicated in selectMode.makeMenus() and selectMolsMode.makeMenus().
        if self.o.jigSelectionEnabled:
            self.Menu_spec.extend( [('Enable Jig Selection',  self.toggleJigSelection, 'checked')])
        else:
            self.Menu_spec.extend( [('Enable Jig Selection',  self.toggleJigSelection, 'unchecked')])
            
        self.Menu_spec.extend( [
            # mark 060303. added the following:
            None,
            ('Change Background Color...', self.w.changeBackgroundColor),
            ])

        self.Menu_spec_shift = list(self.Menu_spec) #bruce 060721 experiment; if it causes no harm, we can
            # replace the self.select item in the copy with one for shift-selecting the chunk, to fix a bug/NFR 1833 ####@@@@
            # (we should also rename self.select)
        
        return # from makeMenus
            
    def setHotSpot_clipitem(self): #bruce 050416; duplicates some code from setHotSpot_mainPart
        """
        set or change hotspot of a chunk in the clipboard
        """
        selatom = self.o.selatom
        if selatom and selatom.element is Singlet:
            selatom.molecule.set_hotspot( selatom) ###e add history message??
            self.o.set_selobj(None)  #bruce 050614-b: fix bug703-related older bug (need to move mouse to see new-hotspot color)
            self.o.gl_update() #bruce 050614-a: fix bug 703 (also required having hotspot-drawing code in chunk.py ignore selatom)
                # REVIEW (possible optim): can gl_update_highlight cover this? It doesn't now cover chunk.selatom drawing,
                # but (1) it could be made to do so, and (2) we're not always drawing chunk.selatom anyway. [bruce 070626]
        ###e also set this as the pastable??
        return        
        
    def setHotSpot_mainPart(self): #bruce 050121 revised this and renamed its menu item #bruce 050614 renamed it
        """
        set hotspot on a main part chunk and copy it (with that hotspot) into clipboard
        """
        # revised 041124 to fix bug 169, by mark and then by bruce
        selatom = self.o.selatom
        if selatom and selatom.element is Singlet:
            selatom.molecule.set_hotspot( selatom)
            
            new = selatom.molecule.copy(None) # None means no dad yet
            #bruce 050531 removing centering:
            ## new.move(-new.center) # perhaps no longer needed [bruce 041206]
            #bruce 041124: open clipboard, so user can see new pastable there
            self.w.mt.open_clipboard()
            
            # now add new to the clipboard
            
            # bruce 050121: first store it in self.pastable, so it will be used
            # as the new pastable if shelf.addmember updates the dashboard,
            # as it does in my local mods to Utility.py; also repeat this down
            # below in case our manual UpdateDashboard is the only one that runs.

            self.pastable = new
            
            # bruce 041124 change: add new after the other members, not before.
            # [bruce 050121 adds: see cvs for history (removed today from this code)
            #  of how this code changed as the storage order of Group.members changed
            #  (but out of sync, so that bugs often existed).]
            
            self.o.assy.shelf.addchild(new) # adds at the end
            self.o.assy.update_parts() # bruce 050316; needed when adding clipboard items.
                # Is this soon enough for UpdateDashboard?? or does it matter if it comes first? ####@@@@
            
            # bruce 050121 don't change selection anymore; it causes too many bugs
            # to have clipboard items selected. Once my new model tree code is
            # committed, we could do this again and/or highlight the pastable
            # there in some other way.
            ##self.o.assy.shelf.unpick() # unpicks all shelf items too
            ##new.pick()

            #Keep the depositState to 'Atoms'. Earlier the depositState was
            #changed to 'Clipboard' because  'Set hotspot and copy' used to 
            #open the clipboard tab in the 'MMKit'. This implementation has 
            #been replaced with a separate 'Paste Mode' to handle Pasting 
            #components. So always keep depositState to Atoms while in 
            #depositMode.  (this needs further cleanup) -- ninad 2007-09-04
            self.w.depositState = 'Atoms'
            
            self.pastable = new # do this again, to influence the following:
            self.UpdateDashboard()
                # (also called by shelf.addchild(), but only after my home mods
                #  to Utility.py get committed, i.e. not yet -- bruce 050121)

            self.w.mt.mt_update() # since clipboard changed
            #bruce 050614 comment: in spite of bug 703 (fixed in setHotSpot_mainPart),
            # I don't think we need gl_update now in this method,
            # since I don't think main glpane shows hotspots and since the user's intention here
            # is mainly to make one in the clipboard copy, not in the main model;
            # and in case it's slow, we shouldn't repaint if we don't need to.
            #   Evidently I thought the same thing in this prior comment, when I removed a glpane update
            # (this might date from before hotspots were ever visible -- not sure):
            ## also update glpane if we show pastable someday; not needed now
            ## [and removed by bruce 050121]
            
                            
        return

    def set_pastable(self, pastable): # no one calls this yet, but they could... [bruce 050121; untested]
        """
        Try to set the current pastable item to the given one
        (which must already be on the clipboard and satisfy is_pastable,
        or this will set the pastable to None, tho the old pastable would
        be a better choice I suppose).
        [Someday this might be useful to call from a model tree context menu command.]
        """
        self.update_pastable()
        oldp = self.pastable
        self.pastable = pastable
        self.UpdateDashboard()
        if not self.pastable is pastable:
            #k (probably this implies self.pastable is None,
            #   but no point in checking this)
            #e someday: history message that we failed
            self.pastable = oldp
            self.UpdateDashboard()
            # if *that* fails, nothing we can do, and it never should
            # (but might if some previously pastable thing
            #  became not pastable somehow, I suppose),
            # so don't bother checking
        return
        
    def select(self): # [this is badly named, since it's very hard to confirm the theory that it's only called from our cmenu.]
        "select the chunk containing the highlighted atom or singlet"
        # bruce 041217 guessed docstring from code
        if self.o.selatom:
            self.o.assy.permit_pick_parts()
            self.o.assy.unpickall_in_GLPane() # was unpickparts; I think this is the intent (and the effect, before now) [bruce 060721]
            self.o.selatom.molecule.pick()
            self.w.win_update()
                                    
    def skip(self): #k needed?
        pass

    pass # end of class depositMode

# end
