# 梦想云每日收益自动推送

基于 GitHub Actions 的梦飞道科技（梦想科技云）每日收益自动推送脚本。

## 功能

- 每天北京时间 9:30 自动运行
- 抓取两个账号的节点状态、昨日收益、利用率数据
- 利用率低于 75% 的节点单独标注告警
- 通过 Server酱 推送到微信

## 配置 Secrets

在仓库 Settings → Secrets and variables → Actions 中配置以下 Secrets：

| Secret 名称 | 说明 |
|------------|------|
| `ACCOUNT1_USERNAME` | 账号1用户名 |
| `ACCOUNT1_PASSWORD` | 账号1密码 |
| `ACCOUNT2_USERNAME` | 账号2用户名 |
| `ACCOUNT2_PASSWORD` | 账号2密码 |
| `SERVERCHAN_KEY` | Server酱 SendKey |

## 手动触发

在 Actions 页面选择 "梦想云每日收益推送" → Run workflow 即可手动触发。
