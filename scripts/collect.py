#!/usr/bin/env python3
"""
聊斋图鉴 - B站数据采集脚本 v2
搜索配置的事件关键词 -> 拉视频列表（标题过滤）-> 拉评论区 -> 聚类 -> 输出 data.json
"""
import json, time, os, sys, re, subprocess
from datetime import datetime

def curl_get(url, timeout=15):
    """通过 Windows curl 发请求，绕过 Python requests 的 TLS 指纹检测"""
    try:
        result = subprocess.run(
            ['/mnt/c/Windows/System32/curl.exe'] if os.path.exists('/mnt/c/Windows/System32/curl.exe') else ['curl'],
            [
                '-s', '--max-time', str(timeout),
                '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                '-H', 'Referer: https://www.bilibili.com/',
                '-H', 'Origin: https://www.bilibili.com',
                '-H', 'Accept: application/json, text/plain, */*',
                '-H', 'Accept-Language: zh-CN,zh;q=0.9',
                url
            ],
            capture_output=True, text=True, timeout=timeout
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"  curl 请求失败: {e}")
        return None

def load_config(config_path="config.json"):
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def search_bilibili(keyword, max_results=30):
    """B站搜索视频"""
    url = f"https://api.bilibili.com/x/web-interface/search/all/v2?keyword={__import__('urllib.parse').quote(keyword)}"
    data = curl_get(url)
    if not data or data.get('code') != 0:
        return []
    
    videos = []
    for result in data['data']['result']:
        for item in result.get('data', []):
            if 'aid' not in item:
                continue
            title = re.sub(r'<[^>]+>', '', item.get('title', '')).strip()
            videos.append({
                'aid': item['aid'],
                'bvid': item.get('bvid', ''),
                'title': title,
                'play': item.get('play', 0),
                'author': item.get('author', ''),
            })
    return videos[:max_results]

def get_comments(aid, max_pages=30):
    """拉取B站视频评论（热度排序，每页20条）
    使用 /x/v2/reply/main?mode=3&pn=N 翻页
    """
    all_comments = []
    for pn in range(1, max_pages + 1):
        url = f"https://api.bilibili.com/x/v2/reply/main?type=1&oid={aid}&mode=3&ps=20&pn={pn}"
        try:
            data = curl_get(url)
            if not data or data.get('code') != 0:
                break
            replies = data['data'].get('replies') or []
            if not replies:
                break
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
            time.sleep(0.25)
        except:
            break
    return all_comments

def is_relevant(video, keywords, title_keywords):
    """判断视频是否真的相关（标题包含事件核心词）"""
    # 如果标题自身包含搜索关键词之一，算相关
    title = video['title']
    for kw in title_keywords:
        if kw in title:
            return True
    # 如果视频播放量极低(<100)且不包含关键词，跳过
    if video['play'] < 500:
        return False
    return False

def cluster_comments(comments):
    """
    基于关键词的评论观点归类
    """
    clusters = {
        "正面/支持": {
            'keywords': ["支持", "看好", "加油", "希望", "期待", "创新", "有魄力", "了不起", "有远见", "敢做", "打破"],
            'color': "#2ecc71"
        },
        "负面/质疑": {
            'keywords': ["不行", "三本", "民办", "割韭菜", "拉倒", "忽悠", "不靠谱", "噱头", "招牌", "垃圾", "坑", "快跑"],
            'color': "#e74c3c"
        },
        "中立/观望": {
            'keywords': ["观望", "看看", "不好说", "看结果", "再看", "拭目以待", "不一定", "难说", "说不准", "等"],
            'color': "#f39c12"
        },
        "对比讨论": {
            'keywords': ["张雪峰", "福耀", "曹德旺", "恒大", "企业家", "企业办学", "王树国", "对比", "不如", "比不"],
            'color': "#3498db"
        },
    }
    
    total = len(comments)
    result = {}
    
    for label, cfg in clusters.items():
        matched = [c for c in comments if any(kw in c['content'] for kw in cfg['keywords'])]
        top = sorted(matched, key=lambda x: x['likes'], reverse=True)[:8]
        result[label] = {
            'count': len(matched),
            'percentage': round(len(matched) / total * 100, 1) if total else 0,
            'color': cfg['color'],
            'representative': [
                {'content': c['content'][:300], 'likes': c['likes'], 'user': c['user']} 
                for c in top
            ]
        }
    
    # 未归类的评论
    all_keywords = set(w for cfg in clusters.values() for w in cfg['keywords'])
    unclassified = [c for c in comments if not any(kw in c['content'] for kw in all_keywords)]
    
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
    
    # 搜索所有关键词下的视频，去重
    seen_aids = set()
    all_videos = []
    bili_kw = event_cfg.get('bilibili_keywords', [])
    # 标题过滤词：至少包含其中一个才算相关
    title_filters = bili_kw + event_cfg.get('title_filters', [])
    
    for kw in bili_kw:
        videos = search_bilibili(kw, max_results=30)
        for v in videos:
            if v['aid'] not in seen_aids:
                seen_aids.add(v['aid'])
                v['_relevant'] = is_relevant(v, bili_kw, title_filters)
                all_videos.append(v)
        time.sleep(0.5)
    
    # 只看相关的视频，忽略跑偏的
    relevant = [v for v in all_videos if v.get('_relevant')]
    if not relevant:
        # 如果没有标题命中的，就用播放量最高的
        relevant = sorted(all_videos, key=lambda x: x['play'], reverse=True)[:10]
        print(f"  无标题精确命中，按播放量取前 {len(relevant)} 个")
    else:
        print(f"  过滤后 {len(relevant)}/{len(all_videos)} 个相关视频")
    
    # 拉取每个视频的评论
    for v in relevant:
        print(f"  拉取评论: [{v['title'][:50]}]...", end=' ', flush=True)
        comments = get_comments(v['aid'], max_pages=20)
        v['comment_count'] = len(comments)
        v['comments'] = comments
        print(f"获 {len(comments)} 条")
        time.sleep(0.3)
    
    # 合并所有评论，去重
    all_comments = []
    seen_texts = set()
    for v in relevant:
        for c in v.get('comments', []):
            key = c['user'] + '|' + c['content'][:60]
            if key not in seen_texts:
                seen_texts.add(key)
                all_comments.append({**c, 'source_video': v['title'][:80]})
    
    print(f"合并去重后共 {len(all_comments)} 条评论")
    
    # 聚类
    clusters = cluster_comments(all_comments)
    
    # 构建输出
    output = {
        'source': 'bilibili',
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
        } for v in relevant],
        'clusters': clusters,
        'total_videos': len(relevant),
        'total_comments': len(all_comments),
    }

    return output


def save_history_snapshot(data, output_dir="events"):
    """追加一条历史快照到 history.json，用于趋势图"""
    event_dir = os.path.join(output_dir, data['event_id'])
    os.makedirs(event_dir, exist_ok=True)
    history_path = os.path.join(event_dir, 'history.json')
    
    clusters = data.get('clusters', {})
    summary = clusters.get('_summary', {})
    
    snapshot = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'total_comments': data['total_comments'],
        'total_videos': data['total_videos'],
    }
    for label, info in clusters.items():
        if label.startswith('_'):
            continue
        snapshot[label] = info['count']
    
    history = []
    if os.path.exists(history_path):
        with open(history_path, 'r', encoding='utf-8') as f:
            try:
                history = json.load(f)
            except:
                history = []
    
    # 同一天不重复追加
    if history and history[-1]['date'] == snapshot['date']:
        history[-1] = snapshot
    else:
        history.append(snapshot)
    
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"历史快照已保存到 {history_path} ({len(history)} 条)")

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
        save_history_snapshot(data, output_dir)
    
    print("\n=== 全部完成 ===")
