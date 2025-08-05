# MobaXterm 配色方案管理工具

本工具提供 MobaXterm 配色方案管理功能，支持从 [iTerm2-Color-Schemes](https://github.com/mbadolato/iTerm2-Color-Schemes) 仓库自动获取和应用配色方案。

## 功能特性

- **自动探测配置**：自动查找 MobaXterm.ini 配置文件
- **配色方案管理**：从 GitHub 仓库获取丰富的配色方案
- **本地缓存**：支持离线使用，提高应用效率
- **自动备份**：应用配色方案前自动备份原配置
- **搜索功能**：支持按名称搜索配色方案
- **状态监控**：查看当前配置和缓存状态

## 安装和配置

### 安装依赖

工具依赖 `gitpython` 库进行 Git 操作，该依赖已包含在项目依赖中：

```bash
# 安装 okit 时会自动安装 gitpython
uv tool install okit
```

### 配置选项

工具支持以下配置选项：

```yaml
# 配置文件路径（可选）
mobaxterm_config_path: "C:/Users/username/AppData/Roaming/Mobatek/MobaXterm/MobaXterm.ini"

# 本地仓库路径（可选）
local_repo_path: "C:/path/to/iterm2-color-schemes"

# 自动更新缓存（可选）
auto_update: false
```

## 使用方法

### 基础命令

```bash
# 查看帮助
okit mobaxterm-colors --help

# 查看状态
okit mobaxterm-colors status

# 管理缓存
okit mobaxterm-colors cache --update
okit mobaxterm-colors cache --clean

# 列出可用配色方案
okit mobaxterm-colors list
okit mobaxterm-colors list --search dark
okit mobaxterm-colors list --limit 50

# 应用配色方案
okit mobaxterm-colors apply --scheme "Dracula"
okit mobaxterm-colors apply --scheme "Solarized Dark" --force
okit mobaxterm-colors apply --scheme "Monokai" --no-backup

# 配置管理
okit mobaxterm-colors config auto-update true
okit mobaxterm-colors config --list
okit mobaxterm-colors config --unset auto-update
```

### 详细使用示例

#### 1. 首次使用

```bash
# 1. 查看当前状态
okit mobaxterm-colors status

# 2. 更新缓存（首次使用需要）
okit mobaxterm-colors cache --update

# 3. 查看可用配色方案
okit mobaxterm-colors list

# 4. 应用配色方案
okit mobaxterm-colors apply --scheme "Dracula"
```

#### 2. 搜索配色方案

```bash
# 搜索包含 "dark" 的配色方案
okit mobaxterm-colors list --search dark

# 搜索包含 "blue" 的配色方案
okit mobaxterm-colors list --search blue

# 显示更多结果
okit mobaxterm-colors list --limit 100
```

#### 3. 应用配色方案

```bash
# 交互式应用（会提示确认）
okit mobaxterm-colors apply --scheme "Dracula"

# 强制应用（跳过确认）
okit mobaxterm-colors apply --scheme "Solarized Dark" --force

# 不创建备份
okit mobaxterm-colors apply --scheme "Monokai" --no-backup
```

#### 4. 缓存管理

```bash
# 更新缓存
okit mobaxterm-colors cache --update

# 清理缓存
okit mobaxterm-colors cache --clean

# 查看缓存状态
okit mobaxterm-colors cache
```

#### 5. 配置管理

工具采用类似 `git config` 的设计，提供灵活的配置管理功能：

```bash
# 设置配置值
okit mobaxterm-colors config auto-update true
okit mobaxterm-colors config mobaxterm_config_path "/custom/path/MobaXterm.ini"

# 获取配置值
okit mobaxterm-colors config auto-update

# 列出所有配置
okit mobaxterm-colors config --list

# 取消设置配置
okit mobaxterm-colors config --unset auto-update
```

**支持的配置项：**

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `auto_update` | bool | false | 是否启用自动更新缓存 |
| `mobaxterm_config_path` | string | null | 自定义 MobaXterm.ini 路径 |

**数据类型支持：**

- **布尔值**：自动识别 `true`/`false`（不区分大小写）
- **字符串值**：所有其他值都作为字符串处理

**使用示例：**

```bash
# 完整配置管理流程
okit mobaxterm-colors config --list                    # 查看当前配置
okit mobaxterm-colors config auto-update true         # 启用自动更新
okit mobaxterm-colors config auto-update              # 验证设置
okit mobaxterm-colors config --unset auto-update      # 取消设置

# 设置自定义配置
okit mobaxterm-colors config custom_setting "value"
okit mobaxterm-colors config debug_mode true
```

## 配置文件探测

工具会自动探测 MobaXterm.ini 配置文件的位置，按以下顺序查找：

1. **用户指定路径**：通过配置项 `mobaxterm_config_path` 指定
2. **默认路径**：
   - `%APPDATA%\Mobatek\MobaXterm\MobaXterm.ini`
   - `%USERPROFILE%\AppData\Roaming\Mobatek\MobaXterm\MobaXterm.ini`
   - `%USERPROFILE%\Documents\MobaXterm\MobaXterm.ini`

如果配置文件不存在，工具会在默认位置创建新文件。

## 配色方案格式

工具支持标准的 MobaXterm 配色方案格式：

```
Color0=0,0,0
Color1=255,255,255
Color2=128,128,128
Color3=192,192,192
...
```

配色方案文件从 [iTerm2-Color-Schemes](https://github.com/mbadolato/iTerm2-Color-Schemes) 仓库的 `mobaxterm` 目录获取。

## 缓存机制

### 缓存位置

缓存文件存储在工具的数据目录中：
```
~/.okit/data/mobaxterm_colors/cache/iterm2-color-schemes/
```

### 缓存更新

- **自动更新**：配置 `auto_update: true` 时，应用配色方案前会自动更新缓存
- **手动更新**：使用 `okit mobaxterm_colors cache --update` 命令
- **离线使用**：缓存存在时支持离线应用配色方案

### 缓存清理

```bash
# 清理缓存
okit mobaxterm_colors cache --clean
```

## 备份机制

### 自动备份

默认情况下，应用配色方案前会自动备份原配置文件：

- **备份位置**：`~/.okit/data/mobaxterm_colors/backups/`
- **备份命名**：`MobaXterm_backup_YYYYMMDD_HHMMSS.ini`
- **禁用备份**：使用 `--no-backup` 参数

### 手动备份

```bash
# 应用配色方案时创建备份
okit mobaxterm_colors apply --scheme "Dracula"
```

## 错误处理

### 常见错误及解决方案

#### 1. 配置文件未找到

**错误信息**：`Could not determine MobaXterm.ini path`

**解决方案**：
- 确认 MobaXterm 已安装
- 手动指定配置文件路径：
  ```bash
  okit mobaxterm-colors config mobaxterm_config_path "C:/path/to/MobaXterm.ini"
  ```

#### 2. 配色方案未找到

**错误信息**：`Color scheme 'scheme_name' not found in cache`

**解决方案**：
- 更新缓存：`okit mobaxterm_colors cache --update`
- 检查配色方案名称：`okit mobaxterm_colors list`
- 使用搜索功能：`okit mobaxterm_colors list --search keyword`

#### 3. Git 操作失败

**错误信息**：`Failed to update cache`

**解决方案**：
- 检查网络连接
- 确认 Git 已安装
- 检查防火墙设置
- 使用本地仓库路径

#### 4. 权限错误

**错误信息**：`Permission denied`

**解决方案**：
- 以管理员权限运行
- 检查文件权限
- 确认目录可写

## 高级配置

### 使用本地仓库

如果网络访问受限，可以指定本地 iTerm2-Color-Schemes 仓库路径：

```bash
# 设置本地仓库路径
okit mobaxterm-colors config local_repo_path "C:/path/to/iterm2-color-schemes"
```

### 自动更新配置

启用自动更新缓存：

```bash
# 启用自动更新
okit mobaxterm-colors config auto_update true

# 禁用自动更新
okit mobaxterm-colors config auto_update false

# 查看当前设置
okit mobaxterm-colors config auto_update
```

## 性能优化

### 缓存策略

- **首次使用**：需要下载完整仓库（约 50MB）
- **后续使用**：仅更新变更文件
- **离线使用**：完全基于本地缓存

### 网络优化

- 使用本地仓库路径避免网络下载
- 配置 Git 代理（如需要）
- 使用镜像仓库（如需要）

## 故障排除

### 诊断命令

```bash
# 查看详细状态
okit mobaxterm-colors status

# 检查缓存状态
okit mobaxterm-colors cache

# 列出可用配色方案
okit mobaxterm-colors list
```

### 日志查看

工具操作日志存储在：
```
~/.okit/data/mobaxterm_colors/logs/
```

### 重置工具

如需完全重置工具：

```bash
# 清理缓存
okit mobaxterm-colors cache --clean

# 删除配置
rm -rf ~/.okit/config/mobaxterm-colors/

# 删除数据
rm -rf ~/.okit/data/mobaxterm-colors/
```

## 常见问题

### Q: 如何找到合适的配色方案？

A: 使用搜索功能查找：
```bash
# 搜索深色主题
okit mobaxterm-colors list --search dark

# 搜索浅色主题
okit mobaxterm-colors list --search light

# 搜索特定颜色
okit mobaxterm-colors list --search blue
```

### Q: 配色方案应用后没有效果？

A: 检查以下项目：
1. 确认 MobaXterm 已重启
2. 检查配置文件路径是否正确
3. 查看备份文件确认更改已应用

### Q: 如何恢复原配置？

A: 从备份文件恢复：
1. 找到备份文件：`~/.okit/data/mobaxterm_colors/backups/`
2. 复制备份文件到 MobaXterm.ini 位置
3. 重启 MobaXterm

### Q: 网络连接问题？

A: 解决方案：
1. 使用本地仓库路径
2. 配置 Git 代理
3. 手动下载仓库到本地

## 技术支持

### 获取帮助

```bash
# 查看命令帮助
okit mobaxterm-colors --help
okit mobaxterm-colors apply --help
okit mobaxterm-colors list --help
okit mobaxterm-colors cache --help
```

### 报告问题

如遇到问题，请提供以下信息：
1. 错误信息
2. 操作系统版本
3. MobaXterm 版本
4. 工具版本：`okit --version`
5. 详细操作步骤

### 贡献配色方案

如需贡献新的配色方案：
1. Fork [iTerm2-Color-Schemes](https://github.com/mbadolato/iTerm2-Color-Schemes) 仓库
2. 在 `mobaxterm` 目录添加 `.mobaxterm` 文件
3. 提交 Pull Request

## 配置管理详解

### Config 命令设计

工具的 `config` 命令采用类似 `git config` 的设计，提供通用和灵活的配置管理功能。

#### 命令格式

```bash
okit mobaxterm-colors config [key] [value] [options]
```

#### 与 Git Config 的对比

| 功能 | Git Config | MobaXterm Colors Config |
|------|------------|-------------------------|
| 设置配置 | `git config key value` | `okit mobaxterm-colors config key value` |
| 获取配置 | `git config key` | `okit mobaxterm-colors config key` |
| 列出配置 | `git config --list` | `okit mobaxterm-colors config --list` |
| 取消设置 | `git config --unset key` | `okit mobaxterm-colors config --unset key` |

#### 高级用法

**批量设置配置：**

```bash
# 使用脚本批量设置
cat > setup_config.sh << 'EOF'
#!/bin/bash
okit mobaxterm-colors config auto_update true
okit mobaxterm-colors config debug_mode false
okit mobaxterm-colors config custom_path "/home/user/custom"
EOF

chmod +x setup_config.sh
./setup_config.sh
```

**配置验证：**

```bash
# 验证关键配置项
required_configs=("auto_update" "mobaxterm_config_path")
for config in "${required_configs[@]}"; do
    value=$(okit mobaxterm-colors config "$config" 2>/dev/null)
    if [ -z "$value" ]; then
        echo "Missing required config: $config"
    fi
done
```

**备份配置：**

```bash
# 导出配置到文件
okit mobaxterm-colors config --list > mobaxterm_config_backup.txt

# 从文件恢复配置
while IFS=':' read -r key value; do
    if [[ $key && $value ]]; then
        okit mobaxterm-colors config "$key" "$value"
    fi
done < mobaxterm_config_backup.txt
```

#### 错误处理

**常见错误：**

1. **配置项不存在**
   ```bash
   $ okit mobaxterm-colors config nonexistent_key
   ⚠ Configuration key 'nonexistent_key' not found
   ```

2. **取消设置不存在的配置项**
   ```bash
   $ okit mobaxterm-colors config --unset nonexistent_key
   ⚠ Configuration key 'nonexistent_key' not found
   ```

#### 最佳实践

1. **使用有意义的配置项名称**
   ```bash
   # 好的命名
   okit mobaxterm-colors config auto_update true
   okit mobaxterm-colors config custom_config_path "/path/to/config"
   
   # 避免的命名
   okit mobaxterm-colors config x true
   okit mobaxterm-colors config path "/path"
   ```

2. **定期清理不需要的配置**
   ```bash
   # 查看所有配置
   okit mobaxterm-colors config --list
   
   # 清理不需要的配置
   okit mobaxterm-colors config --unset unused_setting
   ```

3. **配置文件位置**
   
   配置文件存储在：
   ```
   ~/.okit/config/mobaxterm-colors/config.yaml
   ```

## 更新日志

### v1.1.0
- 改进配置管理功能，采用类似 git config 的设计
- 支持 key-value 格式设置配置
- 添加 --list 和 --unset 选项
- 自动转换布尔值 (true/false)
- 改进缓存验证和自动初始化机制

### v1.0.0
- 初始版本发布
- 支持基础配色方案管理功能
- 实现自动配置探测
- 添加缓存和备份机制 