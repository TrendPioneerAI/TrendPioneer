# WhenRest 免费公开版

## 打开网站

固定前端版本（后台数据持续更新）：
https://rawcdn.githack.com/TrendPioneerAI/TrendPioneer/1d353bf2d06646f150689bade76a8dfb53a83fc6/whenrest/index.html

当前 main 前端（发布后可能存在短时 CDN 缓存）：
https://raw.githack.com/TrendPioneerAI/TrendPioneer/main/whenrest/index.html

首次打开时，托管服务会对所有 HTML 展示 External Content Notice。点击 **Open the page** 即可进入。本网站不要求提供账户密码、Cookie、API Key 或付款信息。

当前为免费公共测试地址，不是已绑定的独立域名。GitHub Pages 自动开通曾返回 Resource not accessible by integration，因此没有宣称 Pages 发布成功。Pages 工作流默认不执行；只有仓库所有者先在平台配置好 Pages，再显式选择 enable_pages，才尝试发布。

## 实际数据覆盖

- Codex：自动采集 codex-resets.com 公开索引中的重置相关记录，保留时间和来源原帖链接，不逐字复制帖子。首次成功采集 51 条。所有记录明确标为第三方索引，不声称是本站独立核验的官方公告。
- OpenAI、Claude、Cursor：读取官方服务状态 JSON，展示对应组件健康度。**服务状态不是额度重置证明。**
- Gemini API：依据官方 RPD 规则计算下一次太平洋午夜，并处理夏令时；不读取项目用量，不适用于 Gemini 聊天套餐。
- Kimi：公开重置源尚未接入，只支持手动个人时间。

## 更新方式

`.github/workflows/whenrest-collect.yml` 配置目标每 5 分钟运行一次，使用 `collect.py` 采集并更新 `data.json`。GitHub 免费调度和缓存可能延迟，不承诺 5 分钟 SLA 或秒级实时性。网站打开时每 60 秒检查当前数据，恢复到前台时也会刷新。点击刷新只重新读取后台最新结果，不会为每位访客单独触发上游抓取。

采集失败会保存错误状态和上次成功结果；超过 15 分钟未成功更新会标记延迟。没有新记录与采集失败是不同状态。robots.txt 禁止抓取时不绕过限制。

任务日志：
https://github.com/TrendPioneerAI/TrendPioneer/actions/workflows/whenrest-collect.yml

公开数据：
https://raw.githubusercontent.com/TrendPioneerAI/TrendPioneer/main/whenrest/data.json

## 免费功能

工具关注、时间线、类型和工具筛选、套餐名称搜索、时区切换、数据源状态、个人倒计时、日历导出、手机适配。个人记录仅保存于当前浏览器；不读取或推断个人账户额度。

不包含支付、购买意向、邮件或短信采集、后台推送、模拟事件、未经校准的概率预测。

## 验证

`test_public.py` 使用真实 Chromium 打开公开网站，通过托管方正常的 Open the page 按钮进入，再从真实网络读取数据。它不拦截请求返回模拟 JSON。检查公开页面、数据读取、筛选、个人时间持久化、日历导出、夏令时以及手机横向溢出；报告与截图保存在 publish-and-verify 工作流产物中。

## 本地维护

```sh
python -m pip install 'requests>=2.32,<3' 'beautifulsoup4>=4.12,<5'
python whenrest/collect.py
python -m http.server 8080 --directory whenrest
```

`index.html` 默认读取公开后台 JSON；源数据保存在公开仓库，不应将任何个人账户信息、认证令牌或用户提交的敏感信息写入这里。
