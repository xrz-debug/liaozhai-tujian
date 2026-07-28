#!/usr/bin/env python3
"""
聊斋图鉴 - HTML 生成器
读取 events/xxx/data.json → 生成 events/xxx/index.html
"""
import json, os, sys
from datetime import datetime

def render_event_page(data):
    """从采集数据生成事件详情 HTML"""
    
    # 聚类颜色映射
    cluster_colors = {
        "正面/支持": "#2ecc71",
        "负面/质疑": "#e74c3c",
        "中立/观望": "#f39c12",
        "对比讨论": "#3498db",
    }
    
    # 视频列表 HTML
    videos_html = ""
    for v in data.get('videos', []):
        videos_html += f"""
        <div class="video-item">
          <a href="{v['url']}" target="_blank">{v['title']}</a>
          <div class="stats">UP主: {v['author']} · 播放: {v['play']:,} · 评论: {v['comment_count']}</div>
        </div>"""
    
    # 聚类 HTML
    clusters = data.get('clusters', {})
    summary = clusters.pop('_summary', {})
    
    clusters_html = ""
    for label, info in clusters.items():
        color = cluster_colors.get(label, "#666")
        reps = info.get('representative', [])
        reps_html = ""
        for r in reps:
            reps_html += f"""
            <div class="comment-item">
              <div class="text">{r['content']}</div>
              <div class="info">@{r['user']} · 👍 {r['likes']}</div>
            </div>"""
        
        clusters_html += f"""
        <div class="cluster-card" style="border-left: 4px solid {color};">
          <h4>{label}</h4>
          <div class="stat">{info['count']} 条 ({info['percentage']}%)</div>
          {reps_html}
        </div>"""
    
    # 无聚类时显示
    if not clusters_html:
        clusters_html = '<p class="empty">暂无数据</p>'
    
    # 恢复 clusters
    data['clusters']['_summary'] = summary
    
    crawl_date = ""
    try:
        dt = datetime.fromisoformat(data['crawl_time'])
        crawl_date = dt.strftime('%Y-%m-%d %H:%M')
    except:
        crawl_date = data.get('crawl_time', '')
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{data['event_title']} - 现代聊斋图鉴</title>
<link rel="stylesheet" href="/liaozhai-tujian/assets/style.css">
</head>
<body>
<header>
  <p><a href="/liaozhai-tujian/" style="color:var(--muted);text-decoration:none;">← 返回首页</a></p>
  <h1>{data['event_title']}</h1>
  <p class="description">{data['event_description']}</p>
</header>

<main>
  <div class="event-header">
    <div class="meta">
      <span>📹 {data['total_videos']} 个相关视频</span>
      <span>💬 {data['total_comments']} 条评论（去重）</span>
      <span>📅 采集于 {crawl_date}</span>
    </div>
  </div>

  <div class="video-list">
    <h3>📺 相关视频</h3>
    {videos_html}
  </div>

  <div class="clusters">
    <h3>🗣️ 评论观点分布</h3>
    {clusters_html}
  </div>
</main>

<footer>
  <p>数据来源：B站评论区 · 观点聚类为关键词归类，仅供参考</p>
  <p>由 Hermes Agent · 现代聊斋图鉴 自动生成</p>
</footer>
</body>
</html>"""
    
    return html

def generate(config_path="config.json", events_dir="events"):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    for event in config['events']:
        if not event.get('enabled', True):
            continue
        event_id = event['id']
        data_path = os.path.join(events_dir, event_id, 'data.json')
        
        if not os.path.exists(data_path):
            print(f"跳过 {event_id}: 无数据文件")
            continue
        
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        html = render_event_page(data)
        html_path = os.path.join(events_dir, event_id, 'index.html')
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"已生成: {html_path}")

if __name__ == '__main__':
    config_path = sys.argv[1] if len(sys.argv) > 1 else 'config.json'
    events_dir = sys.argv[2] if len(sys.argv) > 2 else 'events'
    generate(config_path, events_dir)
