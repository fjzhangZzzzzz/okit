# 发布规范

## 开发与版本

项目采用 `main` 单分支开发。每次提交必须先通过 CI 的构建与测试；未通过 CI 的提交不得生成发布制品。

版本使用 `vMAJOR.MINOR.PATCH`。每个版本 tag 与 Release 均不可复用，且必须指向已经通过 CI 的 `main` 提交。

## GitHub Release 双通道

GitHub Release 的 label 是发布的唯一人工入口：

- `pre-release`：预发布通道。维护者可频繁创建，用于日常安装、升级和验证。
- `latest`：正式通道。仅当预发布版本已验证并达到阶段性目标时设置；它必须沿用同一 tag、commit 和制品，不重新构建。
- `none`：不参与默认通道，只能用精确版本安装或升级。

发布工作流由 Release label 事件触发。创建 `pre-release` 后，工作流重新执行构建、测试和发布；全部成功后才上传 `release-manifest.json` 到固定的 `pre-release` 指针 Release。将该 Release 改为 `latest` 时，工作流仅清理指针，不重建制品。若当前没有预发布版本，预发布指针不存在。

正式与预发布实际制品都保留在各自版本的 Release 中。只有通道指针是可变的；它始终在制品、校验和和发布清单完成后最后更新。

## 无 Token 的安装与升级

公开客户端不调用 GitHub REST Releases API，以避免共享出口 IP 的匿名限流；不要求用户设置 GitHub access token。

固定下载入口如下：

```text
正式通道：releases/latest/download/release-manifest.json
预发布通道：releases/download/pre-release/release-manifest.json
精确版本：releases/download/<tag>/release-manifest.json
```

`okit upgrade` 的规则：

```text
okit upgrade                 # 更新到最新正式版
okit upgrade --prerelease    # 更新到当前预发布版本
okit upgrade --version vX.Y.Z # 更新到指定已发布版本，可用于回退
```

默认更新拒绝降级；指定版本允许安装任意已发布的正式或预发布版本。预发布指针不存在时，`--prerelease` 成功返回“当前没有可用预发布版本”。安装元数据的通道由 Release label 决定，不能由版本号后缀推断。

## 发布产物

每个实际 Release 必须包含 Linux/Windows、amd64/arm64 的归档，及 `checksums.txt`、`release-manifest.json`、`install.sh` 和 `install.ps1`。安装和升级都必须验证校验和；二进制显示的版本、commit 与 manifest 必须一致。

## 操作步骤

1. 将变更提交并推送到 `main`，确认 CI 通过。
2. 在 GitHub Releases 界面为该 commit 创建新 tag 与 Release，并选择 `pre-release`。
3. 等待发布工作流构建、测试、上传制品和更新预发布指针；在预发布环境验证核心使用路径。
4. 验证完成且达到阶段性目标时，在同一 Release 中将 label 设为 `latest`。
5. 若回归，提交修复或发布一个更高版本；也可用 `okit upgrade --version` 安装已验证版本。不得改写已有版本 tag 或制品。
