// Copyright 2007 Nanorex, Inc.  See LICENSE file for details.

#ifndef NV1_H
#define NV1_H

#include <map>
#include <string>
using namespace std;

#include <QtGui>
#include <QMainWindow>
#include <QFileDialog>
#include <QCloseEvent>

#include "Nanorex/Utility/NXCommandLine.h"
#include "Nanorex/Interface/NXEntityManager.h"
using namespace Nanorex;

#include "ResultsWindow.h"
#include "LogHandlerWidget.h"
#include "MainWindowTabWidget.h"
#include "JobManagement/JobMonitor.h"
#include "JobManagement/GROMACS_JobMonitor.h"


/* CLASS: nv1 */
class nv1 : public QMainWindow {
	Q_OBJECT

public:
	nv1(NXEntityManager* entityManager, LogHandlerWidget* logHandlerWidget);
	~nv1();
	
	void processCommandLine(int argc, char *argv[]);

protected:
	void closeEvent (QCloseEvent *event);

public slots:
	void updateMenus();
	void addMonitoredJob(const QString& id, const QString& title);
	void removeMonitoredJob(const QString& id);

private slots:
	void open();
	void about();
	void updateWindowMenu();
	void abortJob(const QString& id);

private:
	NXEntityManager* entityManager;
	
	QMenu* fileMenu;
	QMenu* processMenu;
	QMenu* windowMenu;
	QMenu* helpMenu;
	
	QToolBar* fileToolBar;

	MainWindowTabWidget* mainWindowTabs;
	ResultsWindow* resultsWindow;
	
	// File
	QAction* openAction;
	QAction* exitAction;
	
	// Job Management
	QAction* abortJobAction;
	
	// Window
	QAction* closeAction;
	QAction* closeAllAction;
	QAction* tileAction;
	QAction* cascadeAction;
	QAction* arrangeAction;
	QAction* nextAction;
	QAction* previousAction;
	QAction* separatorAction;
	
	// Help
	QAction* aboutAction;
	
	map<QString, JobMonitor*> jobMonitors;
	
	void createActions();
	void createMenus();
	void createToolBars();
	void createStatusBar();
	void readSettings();
	void writeSettings();
};

#endif
