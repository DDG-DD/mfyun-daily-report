#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
梦飞道科技（梦想科技云）每日收益推送脚本 - GitHub Actions 云端版
从环境变量读取配置，适合在GitHub Actions等云端环境运行
"""

import requests
import json
import datetime
import sys
import os
import base64

# ============== 从环境变量读取配置 ==============

ACCOUNTS = [
    {
        "name": "账号1",
        "username": os.environ.get("ACCOUNT1_USERNAME", ""),
        "password": os.environ.get("ACCOUNT1_PASSWORD", ""),
        "threshold": 75  # 利用率低于75%告警
    },
    {
        "name": "账号2",
        "username": os.environ.get("ACCOUNT2_USERNAME", ""),
        "password": os.environ.get("ACCOUNT2_PASSWORD", ""),
        "threshold": 70  # 利用率低于70%告警
    }
]

PUSH_CONFIG = {
    "method": "serverchan",
    "serverchan_key": os.environ.get("SERVERCHAN_KEY", ""),
}

API_URL = "https://api.mfyun.top/graphql"


def login(username, password):
    query = """
    mutation login($loginForm: LoginInput!) {
      login(loginInput: $loginForm) {
        access_token
        refresh_token
        user_id
      }
    }
    """
    variables = {"loginForm": {"username": username, "password": password}}
    try:
        resp = requests.post(API_URL, json={"query": query, "variables": variables}, timeout=30)
        data = resp.json()
        if "errors" in data:
            print(f"登录失败: {data['errors']}")
            return None
        return data["data"]["login"]["access_token"]
    except Exception as e:
        print(f"登录异常: {e}")
        return None


def get_machine_statistic(token):
    query = """
    query getMachineStatistic {
      online: machines(where: {online: {_eq: 1}}) { data { uuid } total }
      offline: machines(where: {online: {_eq: 0}}) { data { uuid } total }
      total: machines { data { uuid } total }
    }
    """
    headers = {"Authorization": token}
    try:
        resp = requests.post(API_URL, json={"query": query}, headers=headers, timeout=30)
        data = resp.json()
        if "errors" in data:
            print(f"获取节点统计失败: {data['errors']}")
            return None
        result = data["data"]
        return {"total": result["total"]["total"], "online": result["online"]["total"], "offline": result["offline"]["total"]}
    except Exception as e:
        print(f"获取节点统计异常: {e}")
        return None


def get_machine_list(token, date=None):
    if date is None:
        date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    query = """
    query getMachinePage($page: Int!, $pageSize: Int!, $where: MachineBoolExp, $order_by: [MachineOrderBy!]) {
      result: machines(page: $page, page_size: $pageSize, where: $where, order_by: $order_by) {
        data {
          host uuid usage_rate online online_desc max_bandwidth province operator deployed_at remark
          user_bills { profit bill_date total_traffic }
          user { name }
        }
        total
      }
    }
    """
    variables = {
        "page": 1, "pageSize": 100,
        "where": {"user_bills": {"bill_date": {"_eq": date}}},
        "order_by": [{"field": "usage_rate", "order": "desc"}]
    }
    headers = {"Authorization": token}
    try:
        resp = requests.post(API_URL, json={"query": query, "variables": variables}, headers=headers, timeout=30)
        data = resp.json()
        if "errors" in data:
            print(f"获取节点列表失败: {data['errors']}")
            return None
        machines = data["data"]["result"]["data"]
        node_list = []
        for m in machines:
            bills = m.get("user_bills", [])
            profit = bills[0].get("profit") if bills else 0
            traffic = bills[0].get("total_traffic") if bills else 0
            usage_rate = m.get("usage_rate", 0) or 0
            node_list.append({
                "remark": m.get("remark") or "未命名",
                "host": m.get("host", ""),
                "usage_rate": round(usage_rate * 100, 1),
                "online": m.get("online_desc", "未知"),
                "profit": round(profit, 2) if profit else 0,
                "traffic": round(traffic, 3) if traffic else 0,
            })
        return node_list
    except Exception as e:
        print(f"获取节点列表异常: {e}")
        return None


def get_daily_profit(token, user_id, date=None):
    if date is None:
        date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    query = """
    query getBillsPage($page: Int!, $pageSize: Int!, $where: UserBillBoolExp) {
      result: userBills(page: $page, page_size: $pageSize, where: $where) {
        data { id bill_date total_traffic penalty_traffic profit cost }
        total
      }
    }
    """
    variables = {"page": 1, "pageSize": 200, "where": {"bill_date": {"_eq": date}, "user_id": {"_eq": user_id}}}
    headers = {"Authorization": token}
    try:
        resp = requests.post(API_URL, json={"query": query, "variables": variables}, headers=headers, timeout=30)
        data = resp.json()
        if "errors" in data:
            print(f"获取收益失败: {data['errors']}")
            return None
        bills = data["data"]["result"]["data"]
        total_profit = sum(b["profit"] for b in bills if b["profit"])
        total_traffic = sum(b["total_traffic"] for b in bills if b["total_traffic"])
        return {"date": date, "total_profit": round(total_profit, 2), "total_traffic": round(total_traffic, 3), "bill_count": len(bills)}
    except Exception as e:
        print(f"获取收益异常: {e}")
        return None


def get_user_id_from_token(token):
    parts = token.split('.')
    if len(parts) >= 2:
        payload = parts[1] + '=' * (4 - len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded).get("id")
    return None


def push_message(title, content):
    key = PUSH_CONFIG["serverchan_key"]
    if not key:
        print("未配置Server酱 key")
        print(f"标题: {title}\n内容:\n{content}")
        return False
    try:
        url = f"https://sctapi.ftqq.com/{key}.send"
        resp = requests.post(url, data={"title": title, "desp": content}, timeout=30)
        result = resp.json()
        if result.get("code") == 0:
            print("Server酱推送成功")
            return True
        print(f"Server酱推送失败: {result}")
        return False
    except Exception as e:
        print(f"推送异常: {e}")
        return False


def main():
    print("=" * 50)
    print(f"梦飞道科技每日报告 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    account_results = []
    total_profit_all = 0
    
    for account in ACCOUNTS:
        name = account["name"]
        username = account["username"]
        password = account["password"]
        threshold = account["threshold"]
        
        if not username or not password:
            print(f"{name} 未配置，跳过")
            account_results.append({"name": name, "username": username, "error": "未配置", "threshold": threshold})
            continue
        
        print(f"\n--- {name} ({username}) ---")
        token = login(username, password)
        if not token:
            account_results.append({"name": name, "username": username, "error": "登录失败", "threshold": threshold})
            continue
        
        user_id = get_user_id_from_token(token)
        print(f"user_id: {user_id}")
        
        stats = get_machine_statistic(token)
        if stats:
            print(f"节点: 总数{stats['total']} 在线{stats['online']} 离线{stats['offline']}")
        
        profit = get_daily_profit(token, user_id, yesterday)
        if profit:
            print(f"昨日收益: ¥{profit['total_profit']} 流量: {profit['total_traffic']}G")
            total_profit_all += profit["total_profit"]
        
        node_list = get_machine_list(token, yesterday)
        low_usage_nodes = []
        online_nodes = []
        if node_list:
            # 只保留在线节点用于显示
            online_nodes = [n for n in node_list if n["online"] == "在线"]
            # 筛选低利用率节点（在线且低于阈值）
            low_usage_nodes = [n for n in online_nodes if n["usage_rate"] < threshold]
            print(f"节点数: {len(node_list)} 在线: {len(online_nodes)} 低利用率(<{threshold}%): {len(low_usage_nodes)}个")
        
        account_results.append({
            "name": name,
            "username": username,
            "stats": stats,
            "profit": profit,
            "node_list": online_nodes,  # 只传在线节点
            "low_usage_nodes": low_usage_nodes,
            "threshold": threshold
        })
    
    # ============== 构建推送内容 ==============
    print("\n" + "=" * 50)
    title = f"【梦想云日报】{yesterday} 收益¥{round(total_profit_all, 2)}"
    
    content_lines = []
    content_lines.append(f"📅 报告日期: {today}")
    content_lines.append(f"📊 统计周期: {yesterday} 收益数据")
    content_lines.append("")
    
    for result in account_results:
        name = result["name"]
        threshold = result["threshold"]
        
        if "error" in result:
            content_lines.append(f"━━━━━━━━━━━━━━━━━")
            content_lines.append(f"📱 {name}")
            content_lines.append(f"❌ {result['error']}")
            content_lines.append("")
            continue
        
        # 账号标题 + 节点统计
        content_lines.append(f"━━━━━━━━━━━━━━━━━")
        if result.get("stats"):
            s = result["stats"]
            content_lines.append(f"📱 {name} | 节点{s['total']}台(在线{s['online']}/离线{s['offline']})")
        else:
            content_lines.append(f"📱 {name} ({result['username']})")
        
        # 在线点位明细（每个点位一行）
        node_list = result.get("node_list", [])
        if node_list:
            content_lines.append("")
            for i, n in enumerate(node_list, 1):
                warn = "⚠️" if n["usage_rate"] < threshold else "  "
                content_lines.append(f"{i}. {warn}{n['remark']}  利用率{n['usage_rate']}%  收益¥{n['profit']}")
        
        # 账号合计
        if result.get("profit"):
            content_lines.append("")
            content_lines.append(f"💰 {name}合计: ¥{result['profit']['total_profit']}")
        
        # 低利用率告警（单独列出）
        low_nodes = result.get("low_usage_nodes", [])
        if low_nodes:
            content_lines.append("")
            content_lines.append(f"⚠️ 低利用率告警 (<{threshold}%)")
            for n in low_nodes:
                content_lines.append(f"   🔔 {n['remark']}: {n['usage_rate']}% | ¥{n['profit']}")
        
        content_lines.append("")
    
    # 两账号总合计
    content_lines.append("━━━━━━━━━━━━━━━━━")
    content_lines.append(f"💎 两账号总合计: ¥{round(total_profit_all, 2)}")
    
    # 汇总列表
    content_lines.append("")
    content_lines.append("📊 收益汇总列表:")
    for result in account_results:
        if "error" not in result and result.get("profit"):
            content_lines.append(f"   {result['name']}: ¥{result['profit']['total_profit']}")
    content_lines.append(f"   总计: ¥{round(total_profit_all, 2)}")
    
    content = "\n".join(content_lines)
    print(content)
    print("\n" + "=" * 50)
    
    if push_message(title, content):
        print("报告推送完成！")
    else:
        print("报告推送失败！")
        sys.exit(1)


if __name__ == "__main__":
    main()
