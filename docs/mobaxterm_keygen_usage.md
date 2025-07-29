# MobaXterm 密钥生成工具使用指南

## 概述

MobaXterm 密钥生成工具是一个基于 okit 框架的工具，用于生成和管理 MobaXterm 许可证密钥。该工具提供了完整的许可证管理功能，包括密钥生成、验证、激活码生成等。

## 功能特性

- ✅ 生成 MobaXterm 许可证密钥
- ✅ 验证许可证密钥的有效性
- ✅ 生成激活码
- ✅ 管理许可证配置
- ✅ 支持多种输出格式（文本/JSON）
- ✅ 自动保存许可证信息

## 安装

工具已集成到 okit 项目中，安装 okit 后即可使用：

```bash
# 安装 okit
uv tool install okit

# 验证安装
okit --help
```

## 使用方法

### 1. 自动探测 MobaXterm 安装信息

```bash
# 探测系统中安装的 MobaXterm 信息
okit mobaxterm_keygen detect
```

**功能说明：**
- 自动检测系统中安装的 MobaXterm
- 显示安装路径、版本信息
- 检查许可证文件和配置文件
- 支持多种检测方法（注册表、已知路径、环境变量）

**输出示例：**
```bash
正在探测 MobaXterm 安装信息...
✓ 发现 MobaXterm 安装
  安装路径: C:\Program Files\Mobatek\MobaXterm Professional
  版本: 22.0
  检测方法: registry
  显示名称: MobaXterm Professional
  可执行文件: C:\Program Files\Mobatek\MobaXterm Professional\MobaXterm.exe
  许可证文件: C:\Program Files\Mobatek\MobaXterm Professional\Custom\license.txt
  配置文件: C:\Program Files\Mobatek\MobaXterm Professional\MobaXterm.ini
```

### 2. 生成许可证密钥

```bash
# 基本用法
okit mobaxterm_keygen generate --username your_username --version 22.0

# 指定输出文件
okit mobaxterm_keygen generate --username your_username --version 22.0 --output license.txt

# JSON 格式输出
okit mobaxterm_keygen generate --username your_username --version 22.0 --format json --output license.json
```

**参数说明：**
- `--username`: 用户名（必需）
- `--version`: MobaXterm 版本（默认：22.0）
- `--output`: 输出文件路径（可选）
- `--format`: 输出格式，支持 `text` 和 `json`（默认：text）

### 3. 验证许可证密钥

```bash
okit mobaxterm_keygen validate --username your_username --license-key "YOUR-LICENSE-KEY" --version 22.0
```

**参数说明：**
- `--username`: 用户名（必需）
- `--license-key`: 许可证密钥（必需）
- `--version`: MobaXterm 版本（默认：22.0）

### 4. 生成激活码

```bash
okit mobaxterm_keygen activate --username your_username --license-key "YOUR-LICENSE-KEY"
```

**参数说明：**
- `--username`: 用户名（必需）
- `--license-key`: 许可证密钥（必需）

### 5. 列出已保存的许可证

```bash
# 列出所有许可证
okit mobaxterm_keygen list

# 按用户名筛选
okit mobaxterm_keygen list --username your_username
```

### 6. 删除许可证信息

```bash
okit mobaxterm_keygen remove --username your_username
```

## 使用示例

### 示例 1：生成新许可证

```bash
$ okit mobaxterm_keygen generate --username john_doe --version 22.0

============================================================
MobaXterm License Information
============================================================
Username: john_doe
Version: 22.0
Type: Professional
Status: Valid
Created: 2025-07-29T22:37:13.353148
Expires: 2035-07-27T22:37:13.353154

License Key:
AS1L-d5yI-FiG8-Epjo-qlSk-zgnl-ajVB-Y8ZL-WMJ+-x86K-aGg=

Activation Code:
687B1504E2074A33

============================================================
```

### 示例 2：验证许可证

```bash
$ okit mobaxterm_keygen validate --username john_doe --license-key "AS1L-d5yI-FiG8-Epjo-qlSk-zgnl-ajVB-Y8ZL-WMJ+-x86K-aGg="

✓ License key is valid for john_doe
  Username: john_doe
  Version: 22.0
  Type: Professional
  Status: Valid
  Activation Code: 687B1504E2074A33
  Expires: 2035-07-27T22:37:29.159066
```

### 示例 3：生成激活码

```bash
$ okit mobaxterm_keygen activate --username john_doe --license-key "AS1L-d5yI-FiG8-Epjo-qlSk-zgnl-ajVB-Y8ZL-WMJ+-x86K-aGg="

Activation code generated for john_doe
  Username: john_doe
  License Key: AS1L-d5yI-FiG8-Epjo-qlSk-zgnl-ajVB-Y8ZL-WMJ+-x86K-aGg=
  Activation Code: 687B1504E2074A33
```

### 示例 4：管理许可证列表

```bash
# 查看所有许可证
$ okit mobaxterm_keygen list

Found 2 saved license(s):
  Username: john_doe
  Version: 22.0
  Type: Professional
  Status: Valid
  Created: 2025-07-29T22:37:13.353148
  Expires: 2035-07-27T22:37:13.353154
  ----------------------------------------
  Username: jane_smith
  Version: 22.0
  Type: Professional
  Status: Valid
  Created: 2025-07-29T22:40:15.123456
  Expires: 2035-07-27T22:40:15.123456
  ----------------------------------------

# 删除特定用户的许可证
$ okit mobaxterm_keygen remove --username jane_smith

Removed 1 license(s) for username: jane_smith
```

## 技术实现

### 自动探测机制

工具使用多种方法自动探测 MobaXterm 安装信息：

1. **注册表检测**：检查 Windows 注册表中的卸载信息
   - `SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MobaXterm`
   - `SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\MobaXterm`
   - 支持 Home Edition 和 Professional 版本

2. **已知路径检测**：检查常见的安装目录
   - `C:\Program Files (x86)\Mobatek\MobaXterm`
   - `C:\Program Files\Mobatek\MobaXterm`
   - `C:\Program Files (x86)\Mobatek\MobaXterm Professional`
   - `C:\Program Files\Mobatek\MobaXterm Professional`

3. **环境变量检测**：检查 PATH 环境变量中的可执行文件
   - 搜索 `MobaXterm.exe` 在 PATH 中的位置
   - 适用于通过包管理器安装的情况

4. **版本信息获取**：使用 PowerShell 获取文件版本
   ```powershell
   (Get-Item 'MobaXterm.exe').VersionInfo.FileVersion
   ```

### 密钥生成算法

工具使用 PBKDF2 算法生成许可证密钥：

1. **种子生成**：基于用户名、版本和许可证类型生成种子
2. **密钥派生**：使用 PBKDF2-HMAC-SHA256 算法派生密钥
3. **格式化**：Base64 编码并添加分隔符

### 激活码生成

激活码基于用户名和许可证密钥的 SHA256 哈希生成：

```python
activation_data = f"{username}:{license_key}"
hash_obj = hashlib.sha256(activation_data.encode('utf-8'))
activation_code = hash_obj.hexdigest()[:16].upper()
```

### 数据存储

许可证和检测信息自动保存到用户数据目录：

```
~/.okit/data/mobaxterm_keygen/
├── licenses.json          # 许可证信息
└── detection_info.json    # 检测信息
```

## 配置管理

工具使用 okit 框架的配置管理系统：

- **配置目录**：`~/.okit/config/mobaxterm_keygen/`
- **数据目录**：`~/.okit/data/mobaxterm_keygen/`
- **日志目录**：`~/.okit/data/mobaxterm_keygen/logs/`

## 错误处理

工具提供完善的错误处理机制：

- 输入验证：检查必需参数
- 密钥验证：验证许可证密钥格式和有效性
- 文件操作：安全的文件读写操作
- 异常处理：友好的错误信息显示

## 安全注意事项

1. **密钥安全**：生成的许可证密钥仅供学习和测试使用
2. **数据保护**：许可证信息存储在本地，请妥善保管
3. **版本兼容**：确保生成的密钥与目标 MobaXterm 版本兼容

## 故障排除

### 常见问题

1. **许可证验证失败**
   - 检查用户名和版本是否匹配
   - 确认许可证密钥格式正确

2. **文件保存失败**
   - 检查数据目录权限
   - 确保磁盘空间充足

3. **命令未找到**
   - 确认 okit 已正确安装
   - 检查 PATH 环境变量

### 调试模式

使用调试模式获取详细信息：

```bash
okit --log-level DEBUG mobaxterm_keygen generate --username test
```

## 版本历史

- **v1.0.0**: 初始版本，支持基本的密钥生成和验证功能
- **v1.1.0**: 添加激活码生成和许可证管理功能
- **v1.2.0**: 改进错误处理和用户界面

## 许可证

本工具遵循 okit 项目的许可证条款，仅供学习和研究使用。