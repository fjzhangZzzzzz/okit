# 发布规范

## 版本与发布状态

版本只使用以下格式：

- 正式版：`vMAJOR.MINOR.PATCH`
- 预发布版：`vMAJOR.MINOR.PATCH-rc.N`

`N` 从 1 开始递增且不复用。正式版与预发布版必须指向同一提交，正式制品中的版本、commit、文件名和发布清单必须一致。

预发布用于构建和验证。创建 `vX.Y.Z-rc.N` Release 后，发布工作流会运行格式检查、测试、静态检查并上传预发布制品。只有最新 rc 且验证通过的版本才允许升格。

## 升格正式版本

验证完成后，维护者在 GitHub Release 界面执行唯一人工操作：取消“预发布”状态。发布工作流随后会：

1. 校验当前 rc 是该基线的最新候选，并确认正式 tag/Release 不存在；
2. 在相同 commit 上创建 `vX.Y.Z` tag；
3. 用正式 tag 重建制品和 `release-manifest.json`；
4. 校验安装脚本、制品、校验和与版本；
5. 将同一 Release 改为 `vX.Y.Z` 并保留发布说明；
6. 删除该基线下全部 `vX.Y.Z-rc.N` tag 和 Release。

正式构建、上传或校验失败时，工作流恢复预发布状态，保留原 rc 制品并停止清理。清理失败不撤销正式版本，但会报告未清理对象以便重试。

正式 tag 或 Release 已存在时，升格直接拒绝，不覆盖已有正式版本。发布工作流全局串行执行。

## 安装与升级

默认入口只访问 GitHub Releases 的最新正式版本：

```text
https://github.com/fjzhangZzzzzz/okit/releases/latest/download/release-manifest.json
```

精确版本通过 Release 资产访问：

```text
https://github.com/fjzhangZzzzzz/okit/releases/download/<tag>/release-manifest.json
```

示例：

```text
okit upgrade
okit upgrade --version v1.2.3
okit upgrade --version v1.2.3-rc.1
```

不带 `--version` 时，安装和升级只选择最新正式版；没有正式 Release 时直接失败，不回退到预发布版。预发布版本必须显式指定完整版本号，`--prerelease` 不再支持。

从已安装的 rc 升级到对应正式版是正常升级路径。指定版本仍可用于安装已存在的版本或回退到旧正式版。

项目不再使用 GitHub Pages 发布通道、预发布 manifest 或额外 host；客户端只通过 GitHub Releases 的普通 HTTPS 下载 manifest 和制品，不调用 GitHub REST Releases API。

升级发布流程后，先手动运行一次 `.github/workflows/cleanup-pages.yml` 清空历史 Pages 内容，确认部署完成后删除该一次性工作流文件并提交。之后不再启用 GitHub Pages。
