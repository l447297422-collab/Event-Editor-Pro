import argparse
import gzip
import os
import signal
import sys
import traceback
import typing

import evfl
from evfl import EventFlow
import eventeditor.ai as ai
import eventeditor.actor_json as aj
from eventeditor.actor_view import ActorView
from eventeditor.event_view import EventView
from eventeditor.flow_data import FlowData, FlowDataChangeReason
from eventeditor.flowchart_view import FlowchartView
from eventeditor.i18n import tr, set_language, load_from_settings, save_to_settings, language_changed_signal
import eventeditor.util as util
import PyQt5.QtCore as qc # type: ignore
import PyQt5.QtGui as qg # type: ignore
import PyQt5.QtWidgets as q # type: ignore
from . import _version

class Document:
    """存储单个流程图文档的所有数据"""
    def __init__(self, flow: EventFlow, path: str):
        self.flow = flow
        self.path = path
        self.unsaved = False
        self.flow_data = FlowData()
        self.flow_data.setFlow(flow)
        self.widget = None  # 文档容器Widget
        self.inner_tabs = None  # 内部嵌套TabWidget
        self.flowchart_view = None
        self.actor_view = None
        self.event_view = None

class MainWindow(q.QMainWindow):
    def __init__(self, args) -> None:
        super().__init__()
        self.args = args
        self.documents: typing.List[Document] = []  # 多文档列表
        self.current_doc_idx = -1  # 当前活动的文档索引

        self.initMenu()
        self.initWidgets()
        self.initLayout()

        self.updateTitleAndActions()

        self.readSettings()

        self.initVersionInfo()

        language_changed_signal().connect(self._retranslateUi)

    def initVersionInfo(self) -> None:
        versions = _version.get_versions()
        self._version: str = versions['version']
        self._version_rev: str = versions['full-revisionid']

    def show(self) -> None:
        super().show()
        if self.args.event_flow_file:
            self.readFlow(self.args.event_flow_file)

    def initMenu(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu(tr('menu.file'))
        self.new_action = q.QAction(tr('menu.new'), self)
        self.new_action.setShortcut(qg.QKeySequence.New)
        self.new_action.triggered.connect(self.onNewFile)
        file_menu.addAction(self.new_action)
        self.open_action = q.QAction(tr('menu.open'), self)
        self.open_action.setShortcut(qg.QKeySequence.Open)
        self.open_action.triggered.connect(self.onOpenFile)
        file_menu.addAction(self.open_action)
        file_menu.addSeparator()
        self.save_action = q.QAction(tr('menu.save'), self)
        self.save_action.setShortcut(qg.QKeySequence.Save)
        self.save_action.setEnabled(False)
        self.save_action.triggered.connect(self.onSaveFile)
        file_menu.addAction(self.save_action)
        self.save_all_action = q.QAction(tr('menu.save_all'), self)
        self.save_all_action.setShortcut('Ctrl+Shift+S')
        self.save_all_action.setEnabled(False)
        self.save_all_action.triggered.connect(self.onSaveAll)
        file_menu.addAction(self.save_all_action)
        self.save_as_action = q.QAction(tr('menu.save_as'), self)
        self.save_as_action.setShortcut('Ctrl+Alt+S')
        self.save_as_action.setEnabled(False)
        self.save_as_action.triggered.connect(self.onSaveAsFile)
        file_menu.addAction(self.save_as_action)
        self.rename_flow_action = q.QAction(tr('menu.rename_flow'), self)
        self.rename_flow_action.triggered.connect(self.renameFlow)
        file_menu.addAction(self.rename_flow_action)
        file_menu.addSeparator()
        self.exit_action = q.QAction(tr('menu.exit'), self)
        self.exit_action.setShortcut(qg.QKeySequence.Quit)
        self.exit_action.triggered.connect(self.close)
        file_menu.addAction(self.exit_action)

        view_menu = menu.addMenu(tr('menu.flowchart'))
        self.event_name_visible_action = q.QAction(tr('menu.show_event_names'), self)
        self.event_name_visible_action.setCheckable(True)
        self.event_name_visible_action.setChecked(False)
        self.event_name_visible_action.triggered.connect(self.onEventNameVisibilityChanged)
        view_menu.addAction(self.event_name_visible_action)
        self.event_param_visible_action = q.QAction(tr('menu.show_event_parameters'), self)
        self.event_param_visible_action.setCheckable(True)
        self.event_param_visible_action.setChecked(False)
        self.event_param_visible_action.triggered.connect(self.onEventParamVisibilityChanged)
        view_menu.addAction(self.event_param_visible_action)
        view_menu.addSeparator()
        self.reload_graph_action = q.QAction(tr('menu.reload_graph'), self)
        self.reload_graph_action.setShortcut('Ctrl+Shift+R')
        self.reload_graph_action.triggered.connect(self.onReloadGraph)
        view_menu.addAction(self.reload_graph_action)

        self.search_action = q.QAction(tr('menu.search'), self)
        self.search_action.setShortcut('Ctrl+F')
        self.search_action.triggered.connect(self.onSearch)
        view_menu.addAction(self.search_action)
        self.export_graph_action = q.QAction(tr('menu.export_graph'), self)
        self.export_graph_action.triggered.connect(self.onExportGraph)
        view_menu.addAction(self.export_graph_action)
        self.export_definitions_action = q.QAction(tr('menu.export_definitions'), self)
        self.export_definitions_action.triggered.connect(self.onExportDefinitions)
        view_menu.addAction(self.export_definitions_action)
        self.reorder_event_parameters_action = q.QAction(tr('menu.reorder_event_parameters'), self)
        self.reorder_event_parameters_action.triggered.connect(self.onReorderEventParameters)
        view_menu.addAction(self.reorder_event_parameters_action)
        view_menu.addSeparator()
        self.add_event_action = q.QAction(tr('menu.add_event'), self)
        self.add_event_action.triggered.connect(self.onAddEvent)
        view_menu.addAction(self.add_event_action)
        self.add_fork_action = q.QAction(tr('menu.add_fork'), self)
        self.add_fork_action.triggered.connect(self.onAddFork)
        view_menu.addAction(self.add_fork_action)

        language_menu = menu.addMenu(tr('menu.language'))
        self.english_action = q.QAction(tr('menu.english'), self)
        self.english_action.triggered.connect(lambda: self._changeLanguage('en_US'))
        language_menu.addAction(self.english_action)
        self.chinese_action = q.QAction(tr('menu.chinese'), self)
        self.chinese_action.triggered.connect(lambda: self._changeLanguage('zh_CN'))
        language_menu.addAction(self.chinese_action)

        help_menu = menu.addMenu(tr('menu.help'))
        wiki_action = q.QAction(tr('menu.wiki'), self)
        wiki_action.triggered.connect(lambda: qg.QDesktopServices.openUrl(qc.QUrl('https://zeldamods.org')))
        help_menu.addAction(wiki_action)
        github_repo_action = q.QAction(tr('menu.github'), self)
        github_repo_action.triggered.connect(lambda: qg.QDesktopServices.openUrl(qc.QUrl('https://github.com/leoetlino/event-editor')))
        help_menu.addAction(github_repo_action)
        help_menu.addSeparator()
        about_action = q.QAction(tr('menu.about'), self)
        about_action.triggered.connect(self.about)
        help_menu.addAction(about_action)

    def getCurrentDocument(self) -> typing.Optional[Document]:
        """获取当前活动的文档"""
        if self.current_doc_idx >= 0 and self.current_doc_idx < len(self.documents):
            return self.documents[self.current_doc_idx]
        return None

    def _changeLanguage(self, lang_code: str) -> None:
        try:
            if set_language(lang_code):
                save_to_settings()
                self._retranslateUi()
                # 刷新所有文档的UI
                for doc in self.documents:
                    doc.flow_data.actor_model._retranslateUi()
                    doc.flow_data.event_model._retranslateUi()
                    doc.actor_view._retranslateUi()
                    doc.event_view._retranslateUi()
                    if hasattr(doc.flowchart_view, '_retranslateUi'):
                        doc.flowchart_view._retranslateUi()
        except Exception:
            pass

    def _retranslateUi(self) -> None:
        try:
            # Retranslate menus
            menus = self.menuBar().findChildren(q.QMenu)
            for menu in menus:
                title = menu.title()
                if '&File' in title or '&文件' in title:
                    menu.setTitle(tr('menu.file'))
                elif 'Flowc&hart' in title or '&Flowchart' in title or '&流程图' in title:
                    menu.setTitle(tr('menu.flowchart'))
                elif '&Language' in title or '&语言' in title:
                    menu.setTitle(tr('menu.language'))
                elif '&Help' in title or '&帮助' in title:
                    menu.setTitle(tr('menu.help'))

            # Retranslate file menu actions
            self.new_action.setText(tr('menu.new'))
            self.open_action.setText(tr('menu.open'))
            self.save_action.setText(tr('menu.save'))
            self.save_all_action.setText(tr('menu.save_all'))
            self.save_as_action.setText(tr('menu.save_as'))
            self.rename_flow_action.setText(tr('menu.rename_flow'))
            self.exit_action.setText(tr('menu.exit'))

            # Retranslate view menu actions
            self.event_name_visible_action.setText(tr('menu.show_event_names'))
            self.event_param_visible_action.setText(tr('menu.show_event_parameters'))
            self.reload_graph_action.setText(tr('menu.reload_graph'))
            self.export_graph_action.setText(tr('menu.export_graph'))
            self.export_definitions_action.setText(tr('menu.export_definitions'))
            self.reorder_event_parameters_action.setText(tr('menu.reorder_event_parameters'))
            self.add_event_action.setText(tr('menu.add_event'))
            self.add_fork_action.setText(tr('menu.add_fork'))

            # Retranslate language menu actions
            self.english_action.setText(tr('menu.english'))
            self.chinese_action.setText(tr('menu.chinese'))

            # Retranslate all document tabs
            for i, doc in enumerate(self.documents):
                indicator = '*' if doc.unsaved else ''
                self.document_tabs.setTabText(i, f'{indicator}{doc.flow.name}')
                if doc.inner_tabs:
                    doc.inner_tabs.setTabText(0, tr('label.flowchart'))
                    doc.inner_tabs.setTabText(1, tr('label.actors'))
                    doc.inner_tabs.setTabText(2, tr('label.events'))

            self.updateTitleAndActions()
        except Exception as e:
            print(f"Error retranslating UI: {e}")

    def about(self) -> None:
        q.QMessageBox.about(self, tr('about.title'), tr('about.content').format(version=self._version, revision=self._version_rev))

    def initWidgets(self) -> None:
        # 顶层TabWidget作为文档容器
        self.document_tabs = q.QTabWidget(self)
        self.document_tabs.setTabsClosable(True)
        self.document_tabs.tabCloseRequested.connect(self.onCloseDocumentTab)
        self.document_tabs.currentChanged.connect(self.onDocumentTabChanged)

    def initLayout(self) -> None:
        self.setCentralWidget(self.document_tabs)

    def createDocumentWidget(self, doc: Document) -> None:
        """为文档创建UI组件"""
        # 创建文档容器Widget
        doc.widget = q.QWidget()
        doc_layout = q.QVBoxLayout(doc.widget)
        doc_layout.setContentsMargins(0, 0, 0, 0)

        # 内部嵌套TabWidget（包含Flowchart/Actors/Events）
        doc.inner_tabs = q.QTabWidget()
        doc.inner_tabs.setTabPosition(q.QTabWidget.South)

        # 创建Views
        doc.flowchart_view = FlowchartView(self, doc.flow_data)
        doc.actor_view = ActorView(self, doc.flow_data)
        doc.event_view = EventView(self, doc.flow_data)

        # 添加内部Tabs
        doc.inner_tabs.addTab(doc.flowchart_view, tr('label.flowchart'))
        doc.inner_tabs.addTab(doc.actor_view, tr('label.actors'))
        doc.inner_tabs.addTab(doc.event_view, tr('label.events'))

        doc_layout.addWidget(doc.inner_tabs)

        # 连接信号
        def set_unsaved_flag():
            doc.unsaved = True
            self.updateTabTitle(doc)
        doc.flow_data.flowDataChanged.connect(lambda reason: set_unsaved_flag())
        doc.flow_data.flowDataChanged.connect(lambda reason: self.updateTitleAndActions())

        doc.flowchart_view.readySignal.connect(lambda: self.onViewReady(doc))
        doc.flowchart_view.eventSelected.connect(lambda idx: self.onEventSelected(doc, idx))

        doc.actor_view.detail_pane.jumpToEventsRequested.connect(lambda filter_str='': self.onJumpToEventsRequested(doc, filter_str))
        doc.actor_view.jumpToActorEventsRequested.connect(lambda filter_str='': self.onJumpToEventsRequested(doc, filter_str))
        doc.event_view.jumpToFlowchartRequested.connect(lambda idx: self.onJumpToFlowchartRequested(doc, idx))

        doc.inner_tabs.currentChanged.connect(lambda idx: self.onInnerTabChanged(doc, idx))

        # 添加到顶层TabWidget
        tab_name = doc.flow.name
        self.document_tabs.addTab(doc.widget, tab_name)

        # 切换到新文档
        self.current_doc_idx = len(self.documents) - 1
        self.document_tabs.setCurrentIndex(self.current_doc_idx)
        self.updateTitleAndActions()

    def updateTabTitle(self, doc: Document) -> None:
        """更新Tab标题"""
        idx = self.documents.index(doc)
        indicator = '*' if doc.unsaved else ''
        self.document_tabs.setTabText(idx, f'{indicator}{doc.flow.name}')

    def onCloseDocumentTab(self, idx: int) -> None:
        """关闭文档Tab"""
        if idx < 0 or idx >= len(self.documents):
            return

        doc = self.documents[idx]
        if doc.unsaved:
            ret = q.QMessageBox.question(self, tr('message.save_changes'), tr('message.unsaved_changes').format(name=doc.flow.name), q.QMessageBox.Yes | q.QMessageBox.No | q.QMessageBox.Cancel)
            if ret == q.QMessageBox.Cancel:
                return
            if ret == q.QMessageBox.Yes:
                self.writeFlow(doc, doc.path)

        # 移除文档
        self.documents.remove(doc)
        self.document_tabs.removeTab(idx)

        # 更新当前索引
        if len(self.documents) == 0:
            self.current_doc_idx = -1
        elif idx <= self.current_doc_idx:
            self.current_doc_idx = max(0, self.current_doc_idx - 1)

        self.updateTitleAndActions()

    def onDocumentTabChanged(self, idx: int) -> None:
        """切换文档Tab - 性能优化：暂停非活动文档的WebView渲染"""
        # 暂停所有文档的WebView
        for doc in self.documents:
            if doc.flowchart_view:
                doc.flowchart_view.setIsCurrentView(False)

        # 激活新文档
        self.current_doc_idx = idx
        doc = self.getCurrentDocument()
        if doc and doc.flowchart_view:
            doc.flowchart_view.setIsCurrentView(True)

        self.updateTitleAndActions()

    def closeEvent(self, event) -> None:
        """关闭主窗口"""
        # 检查所有未保存的文档
        unsaved_docs = [doc for doc in self.documents if doc.unsaved]
        if unsaved_docs:
            ret = q.QMessageBox.question(self, tr('message.save_changes'), tr('message.unsaved_changes').format(name=f'{len(unsaved_docs)} documents'), q.QMessageBox.Yes | q.QMessageBox.No | q.QMessageBox.Cancel)
            if ret == q.QMessageBox.Cancel:
                event.ignore()
                return
            if ret == q.QMessageBox.Yes:
                for doc in unsaved_docs:
                    self.writeFlow(doc, doc.path)

        self.writeSettings()
        event.accept()

    def readSettings(self) -> None:
        settings = qc.QSettings()
        ai.set_rom_path(settings.value('paths/rom_root'))
        aj.set_actor_definitions_path(settings.value('paths/actor_definitions_root'))
        settings.beginGroup('MainWindow')
        self.resize(settings.value('size', qc.QSize(800, 600)))
        self.move(settings.value('pos', qc.QPoint(200, 200)))
        settings.endGroup()

        settings.beginGroup('flowchart')
        self.event_name_visible_action.setChecked(settings.value('visible_names', False, type=bool))
        self.event_param_visible_action.setChecked(settings.value('visible_params', False, type=bool))
        settings.endGroup()

    def writeSettings(self) -> None:
        settings = qc.QSettings()
        settings.beginGroup('MainWindow')
        settings.setValue('size', self.size())
        settings.setValue('pos', self.pos())
        settings.endGroup()

        settings.beginGroup('flowchart')
        settings.setValue('visible_names', self.event_name_visible_action.isChecked())
        settings.setValue('visible_params', self.event_param_visible_action.isChecked())
        settings.endGroup()

        if aj._actor_definitions_path:
            settings.beginGroup('paths')
            settings.setValue('actor_definitions_root', str(aj._actor_definitions_path))
            settings.endGroup()

    def updateTitleAndActions(self) -> None:
        """更新窗口标题和菜单状态"""
        doc = self.getCurrentDocument()
        if not doc:
            self.setWindowTitle('EventEditor')
            self.save_action.setEnabled(False)
            self.save_as_action.setEnabled(False)
            self.rename_flow_action.setEnabled(False)
            self.reload_graph_action.setEnabled(False)
            self.export_graph_action.setEnabled(False)
            self.export_definitions_action.setEnabled(False)
            self.reorder_event_parameters_action.setEnabled(False)
            self.add_event_action.setEnabled(False)
            self.add_fork_action.setEnabled(False)
        else:
            indicator = '*' if doc.unsaved else ''
            self.setWindowTitle(f'EventEditor - {indicator}{doc.flow.name}')

            has_unsaved = any(d.unsaved and d.path for d in self.documents)
            self.save_action.setEnabled(bool(doc.path))
            self.save_all_action.setEnabled(has_unsaved)
            self.save_as_action.setEnabled(True)
            self.rename_flow_action.setEnabled(bool(doc.path))
            self.reload_graph_action.setEnabled(bool(doc.path))
            self.export_graph_action.setEnabled(True)
            self.export_definitions_action.setEnabled(True)
            self.reorder_event_parameters_action.setEnabled(True)
            self.add_event_action.setEnabled(bool(doc.path))
            self.add_fork_action.setEnabled(bool(doc.path))

    def renameFlow(self) -> None:
        """重命名当前文档的Flow"""
        doc = self.getCurrentDocument()
        if not doc or not doc.flow or not doc.flow.flowchart:
            return
        text, ok = q.QInputDialog.getText(self, tr('dialog.rename'), tr('dialog.rename_prompt'), q.QLineEdit.Normal, doc.flow.name)
        if not ok or not text:
            return
        doc.flow.name = text
        doc.flow.flowchart.name = text
        doc.flow_data.flowDataChanged.emit(FlowDataChangeReason.EventFlowRename)
        self.updateTabTitle(doc)

    def readFlow(self, path: str) -> bool:
        """打开流程图文件，创建新文档Tab"""
        try:
            flow = EventFlow()
            util.read_flow(path, flow)
            doc = Document(flow, path)
            self.documents.append(doc)
            self.createDocumentWidget(doc)
            return True
        except:
            traceback.print_exc()
            q.QMessageBox.critical(self, tr('dialog.open_flowchart'), tr('message.failed_load'))
            return False

    def writeFlow(self, doc: Document, path: str) -> bool:
        """保存文档"""
        if not doc.flow or not path:
            return False

        try:
            util.write_flow(path, doc.flow)
            doc.path = path
            doc.unsaved = False
            self.updateTabTitle(doc)
            self.updateTitleAndActions()
            return True
        except:
            traceback.print_exc()
            q.QMessageBox.critical(self, tr('dialog.save_as'), tr('message.failed_save'))
            return False

    def onNewFile(self) -> bool:
        """创建新文件"""
        path = q.QFileDialog.getSaveFileName(self, tr('dialog.new_file'), '', 'Flowchart (*.bfevfl)')[0]
        if not path:
            return False
        flow = evfl.EventFlow()
        flow.name = 'NewFile'
        flow.flowchart = evfl.Flowchart()
        flow.flowchart.name = 'NewFile'
        try:
            util.write_flow(path, flow)
        except:
            traceback.print_exc()
            q.QMessageBox.critical(self, tr('dialog.new_file'), tr('message.failed_new_file'))
            return False
        return self.readFlow(path)

    def onOpenFile(self) -> bool:
        """打开文件"""
        doc = self.getCurrentDocument()
        default_directory = doc.path if doc else ''
        path = q.QFileDialog.getOpenFileName(self, tr('dialog.open_flowchart'), default_directory, 'Flowchart (*.bfevfl)')[0]
        if path:
            return self.readFlow(path)
        return False

    def onSaveFile(self) -> None:
        """保存当前文档"""
        doc = self.getCurrentDocument()
        if doc:
            self.writeFlow(doc, doc.path)

    def onSaveAll(self) -> None:
        """保存所有未保存的文档"""
        unsaved_docs = [doc for doc in self.documents if doc.unsaved and doc.path]
        if not unsaved_docs:
            return
        for doc in unsaved_docs:
            self.writeFlow(doc, doc.path)

    def onSaveAsFile(self) -> None:
        """另存为"""
        doc = self.getCurrentDocument()
        if doc:
            path = q.QFileDialog.getSaveFileName(self, tr('dialog.save_as'), '', 'Flowchart (*.bfevfl)')[0]
            if path:
                self.writeFlow(doc, path)

    def onInnerTabChanged(self, doc: Document, idx: int) -> None:
        """内部Tab切换"""
        doc.flowchart_view.setIsCurrentView(doc.inner_tabs.widget(idx) == doc.flowchart_view)

    def onViewReady(self, doc: Document) -> None:
        """View准备完成"""
        # 应用当前的显示设置
        self.onEventNameVisibilityChanged()
        self.onEventParamVisibilityChanged()

    def onEventSelected(self, doc: Document, event_idx: int) -> None:
        """选中Event"""
        doc.event_view.selectEvent(event_idx)

    def onJumpToEventsRequested(self, doc: Document, filter_str: str = '') -> None:
        """跳转到Events视图"""
        doc.inner_tabs.setCurrentWidget(doc.event_view)
        if filter_str:
            doc.event_view.search_bar.setValue(filter_str)
            doc.event_view.search_bar.show()

    def onJumpToFlowchartRequested(self, doc: Document, idx: int) -> None:
        """跳转到Flowchart视图"""
        doc.inner_tabs.setCurrentWidget(doc.flowchart_view)
        doc.flowchart_view.selectRequested.emit(idx)

    def onEventNameVisibilityChanged(self) -> None:
        """切换Event名称显示"""
        visible = self.event_name_visible_action.isChecked()
        for doc in self.documents:
            if doc.flowchart_view:
                doc.flowchart_view.eventNameVisibilityChanged.emit(visible)

    def onEventParamVisibilityChanged(self) -> None:
        """切换Event参数显示"""
        visible = self.event_param_visible_action.isChecked()
        for doc in self.documents:
            if doc.flowchart_view:
                doc.flowchart_view.eventParamVisibilityChanged.emit(visible)

    # 菜单操作需要针对当前文档
    def onReloadGraph(self) -> None:
        """重新加载图形"""
        doc = self.getCurrentDocument()
        if doc and doc.flowchart_view:
            doc.flowchart_view.reload()

    def onSearch(self) -> None:
        """打开搜索对话框"""
        doc = self.getCurrentDocument()
        if doc and doc.flowchart_view:
            doc.flowchart_view.search()

    def onExportGraph(self) -> None:
        """导出图形数据"""
        doc = self.getCurrentDocument()
        if doc and doc.flowchart_view:
            doc.flowchart_view.export()

    def onExportDefinitions(self) -> None:
        """导出Actor定义"""
        doc = self.getCurrentDocument()
        if doc and doc.flowchart_view:
            doc.flowchart_view.export_definitions()

    def onReorderEventParameters(self) -> None:
        """重排序Event参数"""
        doc = self.getCurrentDocument()
        if doc and doc.flowchart_view:
            doc.flowchart_view.reorder_event_parameters()

    def onAddEvent(self) -> None:
        """添加Event"""
        doc = self.getCurrentDocument()
        if doc and doc.flowchart_view:
            doc.flowchart_view.addNewEvent()

    def onAddFork(self) -> None:
        """添加Fork"""
        doc = self.getCurrentDocument()
        if doc and doc.flowchart_view:
            doc.flowchart_view.addFork()

def main() -> None:
    qc.QCoreApplication.setOrganizationName('eventeditor')
    qc.QCoreApplication.setApplicationName('eventeditor')
    qc.QSettings.setDefaultFormat(qc.QSettings.IniFormat)

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    parser = argparse.ArgumentParser(prog='eventeditor', description='An event editor for Breath of the Wild')
    parser.add_argument('event_flow_file', nargs='?', help='Event flow file to open')
    args, _ = parser.parse_known_args()

    load_from_settings()

    app = q.QApplication(sys.argv)
    if os.name == 'nt':
        app_font = app.font()
        app_font.setFamily('Segoe UI')
        app_font.setPointSize(int(qg.QFontInfo(app_font).pointSize() * 1.20))
        app.setFont(app_font)
    win = MainWindow(args)
    win.show()
    ret = app.exec_()
    sys.exit(ret)

if __name__ == '__main__':
    main()