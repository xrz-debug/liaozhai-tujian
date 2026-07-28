# 现代聊斋图鉴

网络社会舆论演化追踪。每个事件追踪其在 B站 等平台的舆论演变，记录网络集体叙事。

## 架构

```
config.json          ← 你编辑此文件添加/管理事件
events/
  ├── 事件ID/
  │   ├── data.json     ← 采集数据（自动生成）
  │   └── index.html    ← 事件页面（自动生成）
  └── ...
scripts/
  ├── collect.py       ← B站采集脚本
  └── generate.py      ← HTML 生成脚本
assets/
  └── style.css        ← 样式
index.html             ← 首页（自动读取 config + data 展示）
```

## 添加新事件

编辑 `config.json`，在 `events` 数组中添加一项：

```json
{
  "id": "my-event-id",
  "title": "事件名称",
  "description": "事件简述",
  "bilibili_keywords": ["关键词1", "关键词2"],
  "enabled": true
}
```

## 本地运行

```bash
# 1. 采集数据
python scripts/collect.py

# 2. 生成页面
python scripts/generate.py
```

## 部署到 GitHub Pages

1. 创建 GitHub 仓库 `liaozhai-tujian`
2. 将本项目所有文件推送到仓库
3. 在仓库 Settings → Pages 中启用，Source 选 GitHub Actions
4. GitHub Actions 自动每日运行（见 `.github/workflows/track.yml`）

编辑 `config.json` 添加/删除事件后，推送到 GitHub 即可自动更新。
