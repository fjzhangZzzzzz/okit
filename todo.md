# TODO

记录：
- 待改进的问题
- 待添加的功能

## 待改进的问题

[x] shellconfig 工具的测试中，在 `~/.okit/shellconfig` 目录下生成了测试相关目录并未清理，影响正常使用，该问题可能同样存在于其它工具的测试脚本中。
[ ] 运行测试命令 `uv run pytest tests/ -v` 发现，在 `~/.okit/config` 和 `~/.okit/data` 目录下创建了诸如 `test_tool`、`tool1`、`tool2` 等子目录，应该是测试脚本中创建的测试工具脚本产生，应改进这个问题，对应目录需要在 mock 的临时 okit 根目录下创建。
[ ] 补全命令中，对于 git bash 使用场景，在 ~/.bashrc 中添加的 `source ~/.okit-complete.bash` 可能出现 `~` 解析问题（VSCode打开bash终端提示`bash: C:UsersAdministrator.okit-complete.bash: No such file or directory`），需要将 shellconfig 中关于 git bash 识别、路径转换的部分提取到公共部分，并改进补全工具脚本。
[ ] gitdiffsync 中 --target-root 选项设置的预期是要同步的目标根目录 R，在该根目录下应存在 -s 指定的多个待同步源目录 S1/S2/S3 等，但目前实现将 R 视作待同步目标目录而不是目标目录的父目录，需要修改为预期行为

## 待添加的功能

[x] mobaxterm-colors 工具提供从备份恢复的功能
[ ] 对于复杂命令，大多存在配置需求，比如 shellconfig、mobaxterm-colors，目前做法是每个工具脚本自行实现 config 子命令，子命令中调用 BaseTool 接口进行相关配置操作，考虑在 tool_decorator.py 中统一为复杂命令添加 config 子命令以达到复用效果。
[ ] gitdiffsync 中增加 -d 选项，用于设置待同步目标目录，该选项仅在 --target-root 选项未设置且 -s 仅包含单个待同步源目录时生效，否则无效
