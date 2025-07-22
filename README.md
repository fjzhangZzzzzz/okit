# okit

自用 Python 工具集，作为 UV Tool 扩展分发。

规范：
- 按照类型划分工具目录，每个工具的名称是唯一标识符

## 开发

```bash
git clone https://github.com/fjzhangZzzzzz/okit.git
cd okit

# 修改代码

# 构建 okit
uv build .

# 安装 okit
uv tool install -e .

# 发布到 TestPyPI
uv publish --index testpypi --token YOUR_TEST_TOKEN

# 发布到 PyPI
uv publish --token YOUR_PYPI_TOKEN

# 从 TestPyPI 安装（需指定索引）
uv pip install -i https://test.pypi.org/simple/ okit

# 从正式 PyPI 安装
uv pip install okit
```