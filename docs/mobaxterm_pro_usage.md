# MobaXterm Pro 使用指南

## 概述

MobaXterm Pro 是一个基于 okit 框架的专业许可证管理工具，用于生成和管理 MobaXterm Professional 版本的 Custom.mxtpro 许可证文件。该工具基于参考项目 [ryanlycch/MobaXterm-keygen](https://github.com/ryanlycch/MobaXterm-keygen)，采用简洁高效的设计理念。

## 功能特性

- ✅ 自动探测 MobaXterm 安装信息（路径和版本）
- ✅ 智能解析现有许可证文件内容和版本匹配检查
- ✅ 生成标准的 Custom.mxtpro 许可证文件
- ✅ 一键部署许可证文件到安装目录
- ✅ 支持手动指定版本和输出路径
- ✅ 兼容 MobaXterm 的标准许可证格式
- ✅ 许可证验证和信息显示功能

## 设计理念

本工具回归简单有效的设计理念：
- 专注于生成可用的许可证文件
- 移除不必要的复杂功能
- 提供便捷的自动化部署
- 确保与 MobaXterm 完全兼容

## 安装

工具已集成到 okit 项目中，安装 okit 后即可使用：

```bash
# 安装 okit
uv tool install okit

# 验证安装
okit --help
```

## 使用方法

### 1. 检测 MobaXterm 安装信息

```bash
# 自动检测安装信息（包含路径和版本）
okit mobaxterm-pro detect
```

**功能说明：**
- 自动检测系统中安装的 MobaXterm
- 显示安装路径、版本信息、检测方法
- 智能解析现有许可证文件内容
- 显示许可证详细信息（用户名、版本、类型等）
- 自动比较许可证版本与实际版本，检测版本不匹配
- 提供许可证更新建议
- 支持多种检测方法（注册表、已知路径、环境变量）

**输出示例：**
```bash
# 无license文件的情况
Detecting MobaXterm installation information...
✓ MobaXterm installation found
  Install path: C:\Program Files (x86)\Mobatek\MobaXterm
  Version: 22.0
  Detection method: registry
  Display name: MobaXterm Professional
  Executable file: C:\Program Files (x86)\Mobatek\MobaXterm\MobaXterm.exe
  License file: Not found

# 有license文件的情况（版本匹配）
Detecting MobaXterm installation information...
✓ MobaXterm installation found
  Install path: C:\Users\Administrator\scoop\apps\mobaxterm\current
  Version: 25.2.0.5296
  Detection method: environment
  Package manager: scoop
  Executable file: C:\Users\Administrator\scoop\shims\MobaXterm.exe
  Real executable: C:\Users\Administrator\scoop\apps\mobaxterm\current\MobaXterm.exe
  License file: C:\Users\Administrator\scoop\apps\mobaxterm\current\Custom.mxtpro
    ✓ License file is valid
      Username: TestUser
      Version: 25.2
      License Type: Professional
      User Count: 1
      ✓ Version matches detected MobaXterm version (25.2)

# 有license文件的情况（版本不匹配）
Detecting MobaXterm installation information...
✓ MobaXterm installation found
  Install path: C:\Program Files (x86)\Mobatek\MobaXterm
  Version: 25.2.0.5296
  License file: C:\Program Files (x86)\Mobatek\MobaXterm\Custom.mxtpro
    ✓ License file is valid
      Username: TestUser
      Version: 22.0
      License Type: Professional
      User Count: 1
      ⚠ Version mismatch detected!
        License version: 22.0
        MobaXterm version: 25.2
      The license is for an older version and may not work properly.
      Consider regenerating the license with the current version.
      💡 Regenerate license: okit mobaxterm-pro deploy --username <your_username>
```

### 2. 一键部署许可证（推荐使用）

```bash
# 自动检测并部署到安装目录
okit mobaxterm-pro deploy --username your_username

# 指定版本（可选）
okit mobaxterm-pro deploy --username your_username --version 22.0
```

**功能说明：**
- 自动检测 MobaXterm 安装路径和版本
- 生成 Custom.mxtpro 许可证文件
- 直接部署到安装目录
- 无需手动复制文件

**参数说明：**
- `--username`: 许可证用户名（必需）
- `--version`: MobaXterm 版本（可选，默认使用检测到的版本）

### 3. 手动生成许可证文件

```bash
# 基本用法
okit mobaxterm-pro generate --username your_username --version 22.0 --output Custom.mxtpro

# 生成到当前目录
okit mobaxterm-pro generate --username your_username --version 22.0 --output ./Custom.mxtpro

# 生成到指定路径
okit mobaxterm-pro generate --username your_username --version 22.0 --output /path/to/Custom.mxtpro
```

**参数说明：**
- `--username`: 许可证用户名（必需）
- `--version`: MobaXterm 版本（必需）
- `--output`: 输出文件路径（必需）

## 使用示例

### 示例 1：检测安装信息

```bash
$ okit mobaxterm-pro detect

Detecting MobaXterm installation information...
✓ MobaXterm installation found
  Install path: C:\Program Files (x86)\Mobatek\MobaXterm
  Version: 22.0
  Detection method: registry
  Display name: MobaXterm Professional
  Executable file: C:\Program Files (x86)\Mobatek\MobaXterm\MobaXterm.exe
  License file: Not found
```

### 示例 2：一键部署许可证

```bash
$ okit mobaxterm-pro deploy --username john_doe

Auto-detecting MobaXterm installation...
✓ Found MobaXterm installation
  Path: C:\Program Files (x86)\Mobatek\MobaXterm
  Version: 22.0
  Using detected version: 22.0
✓ License deployed successfully!
  Username: john_doe
  Version: 22.0
  License file: C:\Program Files (x86)\Mobatek\MobaXterm\Custom.mxtpro
Please restart MobaXterm to activate the license.
```

### 示例 3：手动生成许可证文件

```bash
$ okit mobaxterm-pro generate --username john_doe --version 22.0 --output Custom.mxtpro

✓ License file generated successfully!
  Username: john_doe
  Version: 22.0
  Output file: Custom.mxtpro
Please copy the file to MobaXterm's installation directory.
```

## 技术实现

### 许可证文件格式

生成的 `Custom.mxtpro` 文件是一个标准的 ZIP 文件，包含：

```
Custom.mxtpro (ZIP file)
└── Pro.key (text file)
    内容格式：
    [License]
    UserName=john_doe
    Version=22.0
    Key=XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX
```

### 密钥生成算法

使用简化的 MD5 算法生成许可证密钥：

```python
def generate_license_key(self, username: str, version: str) -> str:
    seed = f"{username}{version}MobaXterm"
    hash_obj = hashlib.md5(seed.encode('utf-8'))
    key_base = hash_obj.hexdigest()
    license_key = f"{key_base[:8]}-{key_base[8:16]}-{key_base[16:24]}-{key_base[24:32]}"
    return license_key.upper()
```

### 自动检测机制

工具使用多种方法自动检测 MobaXterm 安装信息：

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

4. **版本信息获取**：使用 PowerShell 获取文件版本
   ```powershell
   (Get-Item 'MobaXterm.exe').VersionInfo.FileVersion
   ```

## 工作流程

### 推荐工作流程（一键部署）

```bash
# 1. 检测安装（可选，了解当前状态）
okit mobaxterm-pro detect

# 2. 一键部署许可证
okit mobaxterm-pro deploy --username your_name

# 3. 重启 MobaXterm 激活许可证
```

### 手动工作流程

```bash
# 1. 检测安装信息
okit mobaxterm-pro detect

# 2. 生成许可证文件
okit mobaxterm-pro generate --username your_name --version 22.0 --output Custom.mxtpro

# 3. 手动复制文件到安装目录
cp Custom.mxtpro "C:\Program Files (x86)\Mobatek\MobaXterm\"

# 4. 重启 MobaXterm 激活许可证
```

## 错误处理

工具提供完善的错误处理机制：

- **安装检测失败**：提供手动检查路径的建议
- **文件生成失败**：检查输出目录权限和磁盘空间
- **部署失败**：检查目标目录的写入权限
- **参数验证**：确保必需参数的完整性

## 故障排除

### 常见问题

1. **MobaXterm 检测不到**
   - 确认 MobaXterm 已正确安装
   - 检查安装路径是否在工具的已知路径列表中
   - 尝试将 MobaXterm 安装目录添加到 PATH 环境变量

2. **文件生成失败**
   - 检查输出目录是否存在且有写入权限
   - 确保磁盘空间充足
   - 确认文件名不包含非法字符

3. **许可证部署失败**
   - 检查 MobaXterm 安装目录的写入权限
   - 确认以管理员权限运行命令提示符
   - 检查防病毒软件是否阻止文件操作

4. **命令未找到**
   - 确认 okit 已正确安装：`uv tool list`
   - 重新安装 okit：`uv tool install okit --force`
   - 检查 PATH 环境变量

### 调试模式

使用调试模式获取详细信息：

```bash
okit --log-level DEBUG mobaxterm-pro detect
okit --log-level DEBUG mobaxterm-pro deploy --username test
```

## 版本兼容性

- **支持的 MobaXterm 版本**：所有主流版本（建议使用 20.0 及以上版本）
- **支持的操作系统**：Windows 10/11
- **Python 版本要求**：Python 3.7+

## 安全注意事项

1. **用途限制**：本工具仅供学习和研究使用
2. **许可证合规**：请遵守 MobaXterm 的许可证条款
3. **文件安全**：生成的许可证文件请妥善保管
4. **权限控制**：建议以管理员权限运行部署命令

## 参考项目

本工具基于以下开源项目：
- [ryanlycch/MobaXterm-keygen](https://github.com/ryanlycch/MobaXterm-keygen)

## 版本历史

- **v2.0.0**: 重新设计，回归简单高效的设计理念
  - 移除复杂的激活码和许可证管理功能
  - 专注于生成标准的 Custom.mxtpro 文件
  - 添加一键部署功能
  - 基于参考项目的简化算法

## 许可证

本工具遵循 okit 项目的许可证条款，仅供学习和研究使用。