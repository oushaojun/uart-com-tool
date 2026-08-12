# uart-com-tool
a uart com tool based on python pyqt5

## 1 how to use
- **1** install python 3.13.14
- **2** 'pip install PyQt5==5.15.11 pyqt5_sip==12.18.0 pyserial==3.5' or 'pip install -r requirements.txt'
- **3** run : python main.py

<img width="1202" height="632" alt="image" src="https://github.com/user-attachments/assets/ad4f50d3-6f0d-4db8-a9bb-6267220ab109" />

## 2 Python PyQt5 串口工具实现总结

### 2.1 项目概述
- 使用Python和PyQt5框架开发的跨平台串口通信工具
- 支持Windows/Linux系统，提供GUI界面进行串口配置和通信
- 主要功能：串口配置、数据收发、日志记录、设置保存

### 2.2 核心技术组件
1. **PyQt5界面框架**
   - 主窗口继承`QMainWindow`
   - 使用`QVBoxLayout`/`QHBoxLayout`进行布局管理
   - 包含`QTextEdit`(输出框)、`QLineEdit`(输入框)、`QComboBox`(下拉选择)等控件

2. **串口通信实现**
   - 基于`pyserial`库(3.5版本)
   - 支持配置项：
     - 端口号(自动检测可用端口)
     - 波特率(9600-115200)
     - 校验位(N/E/O/M/S)
     - 停止位(1/1.5/2)

3. **多线程处理**
   - 使用`QThread`实现后台串口数据接收
   - 通过`pyqtSignal`实现线程间通信
   - 包含线程安全锁(`_log_lock`)保护日志输出

### 2.3 核心功能实现
1. **串口管理**
   - 自动检测可用串口
   - 支持热重连和配置更新
   - 提供打开/关闭串口功能

2. **数据传输**
   - 支持ASCII和HEX格式收发
   - 自动显示收发时间戳和数据长度
   - 错误处理和异常捕获机制

3. **日志系统**
   - 彩色区分收发消息和错误信息
   - 带时间戳和调用位置信息的调试日志
   - 支持日志保存为文本文件

4. **配置持久化**
   - 使用`QSettings`保存配置到INI文件
   - 自动加载上次使用的配置

### 2.4 项目结构
```python
主要类结构：
├── MainWindow(QMainWindow)        # 主窗口
│   ├── SettingsDialog(QDialog)    # 设置对话框
│   └── SerialReadWorker(QObject)  # 串口读取工作线程



