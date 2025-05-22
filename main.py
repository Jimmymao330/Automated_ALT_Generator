import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QFileDialog, QMessageBox, QGroupBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from bs4 import BeautifulSoup

# --- 核心邏輯函數，改為類別並發出訊號 ---
class AltProcessingWorker(QThread):
    """
    用於在單獨的執行緒中處理 HTML，避免 GUI 凍結。
    通過訊號與 GUI 溝通。
    """
    log_signal = pyqtSignal(str) # 用於發送日誌訊息給 GUI
    finished_signal = pyqtSignal(str, int) # 完成時發送輸出路徑和修改數量
    error_signal = pyqtSignal(str) # 發生錯誤時發送錯誤訊息

    def __init__(self, input_html_path, output_html_path, default_alt_text):
        super().__init__()
        self.input_html_path = input_html_path
        self.output_html_path = output_html_path
        self.default_alt_text = default_alt_text

    def run(self):
        self.log_signal.emit("--- 開始處理 ---")
        self.log_signal.emit(f"輸入檔案：{self.input_html_path}")
        self.log_signal.emit(f"輸出檔案：{self.output_html_path}")
        self.log_signal.emit(f"預設 Alt 敘述：'{self.default_alt_text}'")

        try:
            if not os.path.exists(self.input_html_path):
                error_msg = f"錯誤：輸入檔案 '{self.input_html_path}' 不存在。"
                self.log_signal.emit(error_msg)
                self.error_signal.emit(error_msg)
                return

            with open(self.input_html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            soup = BeautifulSoup(html_content, 'html.parser')
            img_tags = soup.find_all('img')

            modified_count = 0
            for img_tag in img_tags:
                current_alt = img_tag.get('alt', '').strip()
                # 如果已經有 alt 屬性且不為空，則跳過，不進行修改
                if current_alt:
                    # 如果需要，這裡可以選擇記錄哪些圖片被跳過
                    # self.log_signal.emit(f"  圖片 '{img_tag.get('src', '無 src 屬性')}' 已有 Alt 敘述，跳過。")
                    continue

                # 如果沒有 alt 屬性或 alt 值為空，則添加或更新 alt 屬性
                img_tag['alt'] = self.default_alt_text
                modified_count += 1
                self.log_signal.emit(
                    f"  已為圖片 '{img_tag.get('src', '無 src 屬性')}' 添加 Alt 敘述: '{self.default_alt_text}'。"
                )

            with open(self.output_html_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))

            self.log_signal.emit("\n--- 處理完成！---")
            self.log_signal.emit(f"共找到 {len(img_tags)} 個 <img> 標籤。")
            self.log_signal.emit(f"已為 {modified_count} 個 <img> 標籤添加 Alt 敘述。")
            self.log_signal.emit(f"修改後的 HTML 已儲存至 '{self.output_html_path}'")
            self.finished_signal.emit(self.output_html_path, modified_count)

        except Exception as e:
            error_msg = f"處理過程中發生錯誤：{e}"
            self.log_signal.emit(error_msg)
            self.error_signal.emit(error_msg)
        finally:
            self.log_signal.emit("--- 處理結束 ---")


# --- GUI 應用程式類別 ---
class AltGeneratorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("網頁圖片 Alt 敘述生成器 (PyQt6)")
        self.setGeometry(100, 100, 700, 550) # x, y, width, height

        self.init_ui()
        self.setAcceptDrops(True) # 啟用拖放

        self.worker = None

    def init_ui(self):
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # 1. 輸入檔案區塊
        input_group = QGroupBox("輸入 HTML 檔案")
        input_layout = QHBoxLayout()
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)

        input_layout.addWidget(QLabel("檔案路徑:"))
        self.input_path_entry = QLineEdit()
        self.input_path_entry.setPlaceholderText("請選擇或拖曳 HTML 檔案到此")
        input_layout.addWidget(self.input_path_entry)

        self.input_path_button = QPushButton("選擇檔案...")
        self.input_path_button.clicked.connect(self.browse_input_file)
        input_layout.addWidget(self.input_path_button)

        # 2. 輸出檔案區塊
        output_group = QGroupBox("輸出 HTML 檔案")
        output_layout = QHBoxLayout()
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)

        output_layout.addWidget(QLabel("儲存路徑:"))
        self.output_path_entry = QLineEdit("output_with_alt.html")
        output_layout.addWidget(self.output_path_entry)

        # 3. Alt 敘述區塊
        alt_group = QGroupBox("Alt 敘述設定")
        alt_layout = QHBoxLayout()
        alt_group.setLayout(alt_layout)
        main_layout.addWidget(alt_group)

        alt_layout.addWidget(QLabel("預設 Alt 文本:"))
        self.default_alt_entry = QLineEdit("圖片內容敘述，請人工校對")
        alt_layout.addWidget(self.default_alt_entry)
        self.default_alt_entry.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # 4. 執行按鈕
        self.run_button = QPushButton("執行生成 Alt 敘述")
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; /* Green */
                color: white;
                padding: 15px 32px;
                text-align: center;
                text-decoration: none;
                font-size: 16px;
                margin: 4px 2px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3e8e41;
            }
        """)
        self.run_button.clicked.connect(self.start_processing)
        main_layout.addWidget(self.run_button)

        # 5. 狀態訊息區
        status_group = QGroupBox("處理狀態與日誌")
        status_layout = QVBoxLayout()
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        main_layout.setStretchFactor(status_group, 1) # 讓日誌區可以擴展

        self.status_text_edit = QTextEdit()
        self.status_text_edit.setReadOnly(True) # 設為只讀
        self.status_text_edit.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        status_layout.addWidget(self.status_text_edit)

    def log_message(self, message):
        """將訊息添加到日誌區域"""
        self.status_text_edit.append(message)

    def browse_input_file(self):
        """開啟檔案對話框，讓使用者選擇 HTML 檔案"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "選擇 HTML 檔案", "", "HTML 檔案 (*.html);;所有檔案 (*.*)"
        )
        if file_path:
            self.input_path_entry.setText(file_path)
            # 自動設定輸出檔案名稱
            dir_name = os.path.dirname(file_path)
            base_name = os.path.basename(file_path)
            name_without_ext, ext = os.path.splitext(base_name)
            output_file_suggestion = os.path.join(dir_name, f"{name_without_ext}_processed{ext}")
            self.output_path_entry.setText(output_file_suggestion)

    def start_processing(self):
        """點擊執行按鈕後呼叫，獲取輸入並啟動處理邏輯（在單獨執行緒中）"""
        input_path = self.input_path_entry.text()
        output_path = self.output_path_entry.text()
        default_alt = self.default_alt_entry.text()

        self.status_text_edit.clear() # 清空之前的狀態訊息

        if not input_path:
            QMessageBox.warning(self, "輸入錯誤", "請選擇一個輸入 HTML 檔案。")
            return
        if not output_path:
            QMessageBox.warning(self, "輸入錯誤", "請指定輸出 HTML 檔案的路徑。")
            return
        if not default_alt.strip():
            QMessageBox.warning(self, "輸入錯誤", "預設 Alt 文本不能為空。")
            return

        # 禁用按鈕以防止重複點擊
        self.run_button.setEnabled(False)

        # 創建並啟動新的執行緒
        self.worker = AltProcessingWorker(input_path, output_path, default_alt)
        self.worker.log_signal.connect(self.log_message)
        self.worker.finished_signal.connect(self.processing_finished)
        self.worker.error_signal.connect(self.processing_error)
        self.worker.start() # 啟動執行緒

    def processing_finished(self, output_path, modified_count):
        """處理完成後的訊號槽"""
        self.run_button.setEnabled(True) # 重新啟用按鈕
        QMessageBox.information(self, "完成",
                                f"HTML 處理完成！\n已為 {modified_count} 個圖片添加 Alt 敘述。\n新檔案儲存於：{output_path}")

    def processing_error(self, error_msg):
        """處理錯誤後的訊號槽"""
        self.run_button.setEnabled(True) # 重新啟用按鈕
        QMessageBox.critical(self, "錯誤", f"處理過程中發生錯誤：\n{error_msg}")

    # --- 拖放事件處理 ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            # 只接受 HTML 檔案
            urls = event.mimeData().urls()
            if all(url.isLocalFile() and url.toLocalFile().endswith(('.html', '.htm')) for url in urls):
                event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            # 我們只處理第一個拖曳進來的 HTML 檔案
            for url in urls:
                if url.isLocalFile() and url.toLocalFile().endswith(('.html', '.htm')):
                    file_path = url.toLocalFile()
                    self.input_path_entry.setText(file_path)
                    # 自動設定輸出檔案名稱
                    dir_name = os.path.dirname(file_path)
                    base_name = os.path.basename(file_path)
                    name_without_ext, ext = os.path.splitext(base_name)
                    output_file_suggestion = os.path.join(dir_name, f"{name_without_ext}_processed{ext}")
                    self.output_path_entry.setText(output_file_suggestion)
                    event.acceptProposedAction()
                    return # 處理第一個檔案後就退出
            event.ignore()
        else:
            event.ignore()


# --- 啟動應用程式 ---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = AltGeneratorApp()
    ex.show()
    sys.exit(app.exec())