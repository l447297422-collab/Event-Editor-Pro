适用于《塞尔达传说：旷野之息》的EventEditorPro
本项目是EventEditor的分支，专注于《塞尔达传说：旷野之息》
相比原版增加了许多功能，旨在提升工作效率与提升体验

相比原版本
1.增加标签页样的多开流程图
2.性能优化
3.增加搜索功能
4.适配简体中文

语言
我们目前适配简体中文与英文，如果你想要适配你的语言，请将json文件提交给我

配置
配置文件存放位置：

Linux或macOS：~/.config/eventeditor/eventeditor.ini

Windows：%APPDATA%/eventeditor/eventeditor.ini

自动补全
《塞尔达传说：旷野之息》
为了启用对actor、action和query的自动补全功能，请在EventEditor的配置文件中添加：

ini
[paths]
rom_root=/path/to/game_rom
其中/path/to/game_rom是一个路径，需要满足
/path/to/game_rom/Pack/Bootup.pack/Actor/AIDef/AIDef_Game.product.sbyml存在。
一个简单且推荐的方法来获取所需的文件结构而无需解压每个存档，是使用botwfstools。

其他游戏
另外，可以通过Flowchart > Export actor definition data to JSON生成JSON actor定义。这将根据当前打开的事件流生成用于自动补全的信息。首次运行此操作时，会弹出提示询问保存此信息的位置。

如果其他事件流包含尚未包含在JSON文件中的actor、action或query，可以安全地重复此操作（已有条目不会被覆盖）。

已知问题
在Linux上，如果主窗口视图在打开文件后仍为完全空白屏幕，请尝试运行QTWEBENGINE_DISABLE_SANDBOX=1 eventeditor来启动工具。

在fork/join状态下取消链接事件大多数情况下会破坏图形生成。因此，当涉及fork/join事件时，不建议使用该选项。

待完成工作
时间线文件（逆向工程）

从EventInfo收集事件信息，并为每个事件流生成元数据文件，以便：

可以自动重新生成EventInfo

可以自动更新事件流的所有副本

节点顺序重排以减少交叉。这曾是dagre.js的一个功能，但后来被移除了……

许可证
本软件根据GNU通用公共许可证第2版或更高版本的条款进行授权。
