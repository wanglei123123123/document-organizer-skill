Document Organizer（整理文档 Skill）

功能
- 按文件扩展名或自定义规则（正则/关键字）把文件移动到目标子目录
- 支持按文件修改时间或创建时间归档到 YYYY/MM 结构
- 支持标签规则：文件名包含关键词则移动到对应目录
- 支持 dry-run（预演），支持 undo（撤销）基于日志的还原
- 配置化：所有规则写在 config.yaml 中，支持扩展

快速开始
1. 环境
   - Python 3.8+
   - 安装依赖：pip install -r requirements.txt

2. 示例配置
   修改 config.yaml 中的规则（示例见 repo 中的 config.yaml）

3. 运行
   - 预演：python organize.py --config config.yaml --src /path/to/docs --dry-run
   - 执行：python organize.py --config config.yaml --src /path/to/docs

4. 撤销（基于最后一条日志）
   python organize.py --undo

配置（快速说明）
- extension_map: 按扩展名映射目标文件夹
- tag_rules: 当文件名包含某些关键词/正则时映射
- date_archive: 是否启用按日期归档（True/False），以及使用 mtime/ctime
- move_or_copy: "move" 或 "copy"
- ignore_patterns: 不处理的文件名模式

注意
- 默认会在 src 下创建目标子目录，脚本会跳过隐藏文件和已存在冲突名（会添加后缀）。
- 强烈建议先用 --dry-run 检查结果。
