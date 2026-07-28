#!/usr/bin/env python3
"""
聊斋图鉴 - B站数据采集脚本
搜索配置的事件关键词 → 拉视频列表 → 拉评论区 → 聚类 → 输出 data.json
"""
import json, requests, time, os, sys, re
from datetime import datetime

BILIBILI_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com/',
}

def load_config(config_path="config.json"):
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def search_bilibili(keyword, max_results=10):
    """B站搜索视频"""
    url = f"https://api.bilibili.com/x/web-interface/search/all/v2?keyword={requests.utils.quote(keyword)}"
    resp = requests.get(url, headers=BILIBILI_HEADERS, timeout=15)
    data = resp.json()
    if data.get('code') != 0:
        return []
    
    videos = []
    for result in data['data']['result']:
        for item in result.get('data', []):
            if 'aid' not in item:
                continue
            title = re.sub(r'<[^>]+>', '', item.get('title', ''))
            videos.append({
                'aid': item['aid'],
                'bvid': item.get('bvid', ''),
                'title': title,
                'play': item.get('play', 0),
                'author': item.get('author', ''),
                'pic': item.get('pic', ''),
            })
    return videos[:max_results]

def get_comments(aid, max_pages=10):
    """拉取B站视频所有热评（每页20条，取前max_pages页）"""
    all_comments = []
    for pn in range(1, max_pages + 1):
        url = f"https://api.bilibili.com/x/v2/reply?type=1&oid={aid}&sort=2&ps=20&pn={pn}"
        try:
            resp = requests.get(url, headers=BILIBILI_HEADERS, timeout=10)
            data = resp.json()
            if data.get('code') != 0:
                break
            replies = data['data'].get('replies') or []
            for r in replies:
                all_comments.append({
                    'user': r.get('member', {}).get('uname', '?'),
                    'uid': r.get('member', {}).get('mid', 0),
                    'content': r.get('content', {}).get('message', ''),
                    'likes': r.get('like', 0),
                    'time': r.get('ctime', 0),
                    'replies': r.get('rcount', 0),
                })
            if len(replies) < 20:
                break
            time.sleep(0.3)
        except:
            break
    return all_comments

def cluster_comments(comments):
    """
    简单基于关键词的评论归类
    返回归类结果 + 各观点代表评论
    """
    # 观点关键词映射
    clusters = {
        "正面/支持": ["支持", "看好", "加油", "希望", "期待", "创新", "有魄力", "了不起", "有远见"],
        "负面/质疑": ["不行", "三本", "民办", "割韭菜", "拉倒", "忽悠", "不靠谱", "噱头", "招牌"],
        "中立/观望": ["观望", "看看", "不好说", "看结果", "再看", "拭目以待", "不一定"],
        "对比讨论": ["张雪峰", "福耀", "玻璃", "许家印", "恒大", "曹德旺", "企业家", "企业办学"],
    }
    
    total = len(comments)
    result = {}
    
    for label, keywords in clusters.items():
        matched = [c for c in comments if any(kw in c['content'] for kw in keywords)]
        top = sorted(matched, key=lambda x: x['likes'], reverse=True)[:5]
        result[label] = {
            'count': len(matched),
            'percentage': round(len(matched)/total*100, 1) if total else 0,
            'representative': [{'content': c['content'][:200], 'likes': c['likes'], 'user': c['user']} for c in top]
        }
    
    # 未归类的评论
    all_keywords = set(w for kw in clusters.values() for w in kw)
    unclassified = [c for c in comments if not any(kw in c['content'] for kw in all_keywords)]
    
    # 总的统计
    result['_summary'] = {
        'total_comments': total,
        'classified': total - len(unclassified),
        'unclassified': len(unclassified),
    }
    
    return result

def build_event_data(event_cfg):
    """对一个事件执行完整采集流水线"""
    event_id = event_cfg['id']
    print(f"\n=== 采集事件: {event_cfg['title']} ===")
    
    # 1. 搜索所有关键词下的视频，去重
    seen_aids = set()
    all_videos = []
    for kw in event_cfg.get('bilibili_keywords', []):
        videos = search_bilibili(kw, max_results=10)
        for v in videos:
            if v['aid'] not in seen_aids:
                seen_aids.add(v['aid'])
                all_videos.append(v)
        time.sleep(0.5)
    
    print(f"找到 {len(all_videos)} 个相关视频")
    
    # 2. 拉取每个视频的评论
    for v in all_videos:
        print(f"  拉取评论: {v['title'][:40]}...")
        comments = get_comments(v['aid'], max_pages=5)
        v['comment_count'] = len(comments)
        v['comments'] = comments
        time.sleep(0.3)
    
    # 3. 合并所有评论，去重
    all_comments = []
    seen_texts = set()
    for v in all_videos:
        for c in v.get('comments', []):
            # 简单的去重
            key = c['user'] + '|' + c['content'][:50]
            if key not in seen_texts:
                seen_texts.add(key)
                all_comments.append({**c, 'source_video': v['title'][:60]})
    
    print(f"合并去重后共 {len(all_comments)} 条评论")
    
    # 4. 聚类
    clusters = cluster_comments(all_comments)
    
    # 5. 构建输出
    output = {
        'event_id': event_id,
        'event_title': event_cfg['title'],
        'event_description': event_cfg.get('description', ''),
        'crawl_time': datetime.now().isoformat(),
        'videos': [{
            'aid': v['aid'],
            'bvid': v.get('bvid', ''),
            'title': v['title'],
            'play': v['play'],
            'author': v['author'],
            'comment_count': v.get('comment_count', 0),
            'url': f"https://www.bilibili.com/video/{v.get('bvid', 'av' + str(v['aid']))}",
        } for v in all_videos],
        'clusters': clusters,
        'total_videos': len(all_videos),
        'total_comments': len(all_comments),
    }
    
    return output

def save_event(data, output_dir="events"):
    """保存事件数据到 JSON 文件"""
    event_dir = os.path.join(output_dir, data['event_id'])
    os.makedirs(event_dir, exist_ok=True)
    
    path = os.path.join(event_dir, 'data.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"数据已保存到 {path}")
    return path

if __name__ == '__main__':
    config_path = sys.argv[1] if len(sys.argv) > 1 else 'config.json'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'events'
    
    config = load_config(config_path)
    
    for event in config['events']:
        if not event.get('enabled', True):
            continue
        data = build_event_data(event)
        save_event(data, output_dir)
    
    print("\n=== 全部完成 ===")
