# Copyright (c) 2004 Nanorex, Inc.  All rights reserved.

from SimSetupDialog import *
from fileIO import writemmp
from commands import *
from debug import *
import os, sys, re, signal

def fileparse(name):
    """breaks name into directory, main name, and extension in a tuple.
    fileparse('~/foo/bar/gorp.xam') ==> ('~/foo/bar/', 'gorp', '.xam')
    """
    m=re.match("(.*\/)*([^\.]+)(\..*)?",name)
    return ((m.group(1) or "./"), m.group(2), (m.group(3) or ""))
    
    
class runSim(SimSetupDialog):
    def __init__(self, assy):
        SimSetupDialog.__init__(self)
        self.assy = assy
        self.nframes = 900
        self.temp = 300
        self.stepsper = 10
        self.timestep = 10
        self.fileform = ''
        self.mext = '.xyz'


    def saveFilePressed(self):
        if self.assy.filename:
#            dir, fil, ext = fileparse(self.assy.filename)
            sdir = self.assy.filename
        else: 
#            dir, fil = "./", self.assy.name
            sdir = globalParms['WorkingDirectory']

        if self.mext == ".xyz": sfilter = QString("XYZ Format (*.xyz)")
        else: sfilter = QString("Data Part Binary (*.dpb)")
        
        fn = QFileDialog.getSaveFileName(sdir,
                    "XYZ Format (*.xyz);;Data Part Binary (*.dpb)",
                    self, "IDONTKNOWWHATTHISIS",
                    "Save As",
                    sfilter)
        
        if fn:
            fn = str(fn)
            dir, fil, ext2 = fileparse(fn)
            ext =str(sfilter[-5:-1]) # Get "ext" from the sfilter. It *can* be different from "ext2"!!! - Mark
            safile = dir + fil + ext # full path of "Save As" filename
            
            if os.path.exists(safile): # ...and if the "Save As" file exists...

                # ... confirm overwrite of the existing file.
                ret = QMessageBox.warning( self, self.name(),
                        "The file \"" + fil + ext + "\" already exists.\n"\
                        "Do you want to overwrite the existing file or cancel?",
                        "&Overwrite", "&Cancel", None,
                        0,      # Enter == button 0
                        1 )     # Escape == button 1

                if ret==1: # The user cancelled
                    self.assy.w.statusBar.message( "Cancelled.  File not saved." )
                    return # Cancel clicked or Alt+C pressed or Escape pressed
            
            self.mext = ext

            if ext == '.dpb': # DPB file format
                ftype = 'DPB'
                self.fileform = ''
            else: # XYZ file format
                ftype = 'XYZ'
                self.fileform = '-x'

            self.hide() # Hide simulator dialog window.
            
            r = self.saveMovie(safile)
            
            if not r: # Movie file saved successfully.
                self.assy.w.statusBar.message( ftype + " file saved: " + safile)


    def createMoviePressed(self):
        """Creates a DPB (movie) file of the current part.  
        The part does not have to be saved
        as an MMP file first, as it used to.
        """
        QDialog.accept(self)
        if self.assy.filename: # Could be MMP or PDB file.
            moviefile = self.assy.filename[:-4] + '.dpb'
        else: 
            tmpFilePath = self.assy.w.tmpFilePath # ~/nanorex directory
            moviefile = os.path.join(tmpFilePath, "Untitled.dpb")

        r = self.saveMovie(moviefile)
        
        if not r: # Movie file saved successfully.
            msg = "Total time to create movie file: %d seconds" % self.assy.w.progressbar.duration
            self.assy.w.statusBar.message(msg) 
            msg = "Movie written to [" + moviefile + "]."\
                        "To play movie, click on the <b>Movie Player</b> <img source=\"movieicon\"> icon."
            # This makes a copy of the movie tool icon to put in the HistoryMegawidget.
            QMimeSourceFactory.defaultFactory().setPixmap( "movieicon", 
                        self.assy.w.toolsMoviePlayerAction.iconSet().pixmap() )
            self.assy.w.statusBar.message(msg)
            
            self.assy.moviename = moviefile

        return

    def saveMovie(self, moviefile):
        """Creates a moviefile.  
        A moviefile can be either a DPB file or an XYZ trajectory file.
        A DPB file is a binary trajectory file. An XYZ file is a text file.
        """
        # When creating a movie file, we cwd to tmpFilePath and spawn the
        # simulator.  The reason we do this is because os.spawn on Win32
        # systems will not work if there are spaces in any of the arguments
        # supplied to it.  Often, there are spaces in the file and directory
        # names on Win32 systems.  To get around this problem, we chdir to 
        # assy.w.tmpFilePath and run the simulator on "mmpfile", generating "dpbfile".
        # Then we rename dpbfile to moviefile and return to the original working directory.
        #
        # Note: If "moviefile" is an XYZ trajectory file, the simulator writes directly to
        # the file without renaming it.  This is because the progress bar often completes
        # before the spawned simulator completes writing the file.  If we attempt to 
        # rename the file before the simulator has completed, we get a "permission 
        # denied" error.  The only problem with this is when the moviefile has a space,
        # which can definitely happen.  This is current a bug that will be fixed soon.
        # - Mark 050106
        
        
        # Wait (hourglass) cursor
        QApplication.setOverrideCursor( QCursor(Qt.WaitCursor) )
        
        # When creating an XYZ trajectory file, we want the simulator to write directly to
        # the file.  When creating a DPB file, we cwd to tmpFilePath and spawn the
        # simulator.  It write "
        if self.fileform == "-x": dpbfile = moviefile
        else: dpbfile = "simulate.dpb"
        
        mmpfile = "simulate.mmp" # We always save the current part to an MMP file.
        
        filePath = os.path.dirname(os.path.abspath(sys.argv[0]))
        
        # This full path to the simulator executable.
        program = os.path.normpath(filePath + '/../bin/simulator')
        
        # Args for the simulator.  THE TIME STEP ARGUMENT IS MISSING ON PURPOSE.
        # The time step (-s) argument is not currently supported.
        args = [program, '-f' + str(self.nframes), '-t' + str(self.temp), '-i' + str(self.stepsper), str(self.fileform),  '-o' + dpbfile, mmpfile]
        
        
        basename = os.path.basename(moviefile) # "filename.dpb" or "filename.xyz"
        
        # Tell user we're creating the movie file...
        msg = "<span style=\"color:#006600\">Simulator: Creating movie file [" + moviefile + "]</span>"
        self.assy.w.statusBar.message(msg)

        # On Win32, spawnv() has problems with a space in an argument, and
        # tmpFilePath usually has a space for Win32 systems.
        # We solve this by changing cwd to tmpFilePath, running the simulator, 
        # move the moviefile to the final location, then returning to the original wd.
        #   - Mark 050105.
        oldWorkingDir = os.getcwd()
        tmpFilePath = self.assy.w.tmpFilePath # ~/nanorex directory
        os.chdir(tmpFilePath)
            
        # READ THIS IF YOU PLAN TO CHANGE ANY CODE FOR saveMovie!
        # The placement of writemmp here is strategic.  It must come after changing
        # to "tmpFilePath" and before computing "natoms".   This ensures that saveMovie
        # will work when creating a movie for a file without an assy.alist.  Examples of this
        # situation include:
        # 1)  The part is a PDB file.
        # 2) We have chunks, but no assy.alist.  This happens when the user opens a 
        #      new part, creates something and simulates before saving as an MMP file.
        # 
        # I do not know if it was intentional, but assy.alist is not created until an mmp file 
        # is created.  In the future, it would be nice to 
        #
        writemmp(self.assy, mmpfile, False)
        natoms = len(self.assy.alist)
            
        # Based on the way simulator.c writes an XYZ trajectory file, 
        # it is impossible to determine the exact final size.
        # This formula is an estimate.  "filesize" should never be larger than the
        # actual final size of the XYZ file, or the progress bar will never hit 100%,
        # even tho the simulator finished writing the file.
        # - Mark 050105 
        if self.fileform == "-x": 
            dpbfile = moviefile
            filesize = self.nframes * ((natoms * 32) + 25) # xyz filesize (estimate)
        else: 
            filesize = (self.nframes * natoms * 3) + 4 # dpb filesize (exact)
            
        if os.path.exists(dpbfile): os.remove (dpbfile) # Delete before spawning simulator.
        
#        print  "program = ",program
#        print  "Spawnv args are %r" % (args,) # this %r remains (see above)
        
        try:
            kid = os.spawnv(os.P_NOWAIT, program, args)
            r = self.assy.w.progressbar.launch(filesize, dpbfile, "Simulate", "Writing movie file " + basename + "...", 1)
            s = None
            
            # If we have written a dbp (not xyz) file, delete moviefile so we can rename (move) dpbfile to moviefile.
            if not r and self.fileform != "-x":   
                if os.path.exists(moviefile): os.remove (moviefile)
                os.rename (dpbfile, moviefile)
        
        except:
            print_compact_traceback("exception in simulation; continuing: ")
            s = "internal error (traceback printed elsewhere)"
            r = -1 # simulator failure
        
        # Change back to working directory.
        os.chdir(oldWorkingDir)
        QApplication.restoreOverrideCursor() # Restore the cursor
        
        if not r: return r # Main return
        
        if r == 1: # User pressed Abort button in progress dialog.
            self.assy.w.statusBar.message("<span style=\"color:#ff0000\">Simulator: Aborted.</span>")         
            # We should kill the kid, but not sure how on Windows
            if sys.platform not in ['win32']: os.kill(kid, signal.SIGKILL) # Not tested - Mark 050105
            
        else: # Something failed...
            if not s: msg = "<span style=\"color:#ff0000\">Simulation failed: exit code %r </span>" % r
            self.assy.w.statusBar.message(msg)

        return r

    def NumFramesValueChanged(self,a0):
        """Slot from the spinbox that changes the number of frames for the simulator.
        """
        self.nframes = a0

    def StepsChanged(self,a0):
        """Slot from the spinbox that changes the number of steps for the simulator.
        """
        self.stepsper = a0

    def TemperatureChanged(self,a0):
        """Slot from the spinbox that changes the temperature for the simulator.
        """
        self.temp = a0

    def TimeStepChanged(self,a0):
        """Slot from the spinbox that changes time step for the simulator.
        """
        # THIS PARAMETER IS CURRENTLY NOT USED BY THE SIMULATOR
        # - Mark 050106
        self.timestep = a0