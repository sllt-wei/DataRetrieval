import os
import json
import requests
from common.log import logger
import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from plugins import *
from typing import Dict, Any, List
from datetime import datetime

@plugins.register(
    name="DataRetrieval",
    desc="数据查询（支持票房和股票）",
    version="2.1",
    author="sllt",
    desire_priority=500
)
class DataRetrieval(Plugin):
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
    APIs = {
        "box_office": "http://shanhe.kim/api/za/piaofang.php",
        "stock_data": "https://api.pearktrue.cn/api/stock/",
        "us_stock_quote": "https://api.stockdata.org/v1/data/quote"
    }

    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        # config 是加载后的配置字典
        config = self.load_config()  # 根据实际情况加载配置
        self.US_STOCK_API_TOKEN = config.get("us_stock_api_token", "")
        logger.info(f"[{__class__.__name__}] 插件初始化成功")

    def on_handle_context(self, e_context):
        context = e_context["context"]
        if context.type != ContextType.TEXT:
            return

        content = context.content.strip().lower()
        
        if content == "票房":
            self._handle_box_office(e_context)
        elif content.startswith("股票"):
            self._handle_stock(e_context)
        elif content.startswith("美股"):
            self._handle_us_stock(e_context)
            
    def _handle_us_stock(self, e_context):
        """
        处理美股数据查询，示例命令格式：
        美股 AAPL
        """
        parts = e_context["context"].content.strip().split()
        if len(parts) < 2:
            return self._send_reply(e_context, "⚠️ 请输入正确格式：美股 股票代码\n例：美股 AAPL")
    
        symbol = parts[1].upper()
        params = {
            "api_token": self.US_STOCK_API_TOKEN,  # 必须提供有效的 API 令牌
            "symbols": symbol,
            # extended_hours 可根据需求设置为 true 包含盘前盘后数据，此处设置为 false
            "extended_hours": "false",
            # 按股票代码键入返回结果
            "key_by_ticker": "true"
        }
    
        try:
            response = requests.get(self.APIs["us_stock_quote"], params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"[FinancialData] US Stock API 请求失败: {str(e)}")
            return self._send_reply(e_context, "⚠️ 获取美股数据失败，请稍后重试")
    
        # 判断返回数据是否有效
        if not data.get("data") or symbol not in data["data"]:
            return self._send_reply(e_context, "⚠️ 未找到该股票数据")
    
        us_data = data["data"][symbol]
        # 解析时间并转换格式
        raw_time = us_data.get('last_trade_time', 'N/A')
        formatted_time = "N/A"
        if raw_time != 'N/A':
            try:
                time_obj = datetime.strptime(raw_time, "%Y-%m-%dT%H:%M:%S.%f")
                formatted_time = time_obj.strftime("%Y年%m月%d日 %H:%M:%S")
            except ValueError:
                formatted_time = raw_time  # 如果转换失败，保持原样

        reply_text = f"📊 {us_data.get('name', symbol)} ({us_data.get('ticker', symbol)})\n"
        reply_text += f"最新价格：{us_data.get('price', 'N/A')} USD\n"
        reply_text += f"开盘价：{us_data.get('day_open', 'N/A')} USD\n"
        reply_text += f"当日最高：{us_data.get('day_high', 'N/A')}  当日最低：{us_data.get('day_low', 'N/A')} USD\n"
        reply_text += f"52周最高：{us_data.get('52_week_high', 'N/A')}  52周最低：{us_data.get('52_week_low', 'N/A')} USD\n"
        # 仅当 market_cap 不为 None 时才显示
        market_cap = us_data.get('market_cap')
        if market_cap and str(market_cap).lower() not in ["none", "null", "0"]:
                reply_text += f"市值：{market_cap} USD\n"
        # reply_text += f"市值：{us_data.get('market_cap', 'N/A')}\n"
        reply_text += f"成交量：{us_data.get('volume', 'N/A')}\n"
        reply_text += f"前收盘价：{us_data.get('previous_close_price', 'N/A')} USD\n"
        reply_text += f"涨跌幅：{us_data.get('day_change', 'N/A')}%\n"
        reply_text += f"最后交易时间：{formatted_time}\n"
    
        e_context["reply"] = Reply(ReplyType.TEXT, reply_text)
        e_context.action = EventAction.BREAK_PASS


    def _handle_box_office(self, e_context):
        """处理票房查询"""
        data = self._fetch_data("box_office")
        logger.debug("Fetched box office data: %s", data)
        if data.get("code") != "200":
            return self._send_reply(e_context, "⚠️ 获取票房数据失败，请稍后重试")

        reply_text = self._format_box_office(data)
        e_context["reply"] = Reply(ReplyType.TEXT, reply_text)
        e_context.action = EventAction.BREAK_PASS

    def _handle_stock(self, e_context):
        """处理股票查询"""
        parts = e_context["context"].content.strip().split()
        if len(parts) < 2:
            return self._send_reply(e_context, "⚠️ 请输入正确格式：股票 代码 [数量]\n例：股票 300033 5")

        try:
            secid = parts[1]
            num = int(parts[2]) if len(parts) > 2 else 5
            num = max(1, min(num, 50))  # 限制查询数量1-50
        except ValueError:
            return self._send_reply(e_context, "⚠️ 数量参数需为整数")

        params = {"secid": secid, "num": num}
        data = self._fetch_data("stock_data", params)
        
        if not data or data.get("code") != 200:
            return self._send_reply(e_context, "⚠️ 获取股票数据失败，请检查代码是否正确")

        reply_text = self._format_stock(data, num)
        e_context["reply"] = Reply(ReplyType.TEXT, reply_text)
        e_context.action = EventAction.BREAK_PASS

    def _fetch_data(self, api_type: str, params: dict = None) -> Dict:
        """通用数据获取方法"""
        try:
            response = requests.get(
                self.APIs[api_type],
                params=params,
                timeout=15
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"[FinancialData] API请求失败: {str(e)}")
            return {}

    def _format_box_office(self, data: Dict) -> str:
        """格式化票房数据，返回指定格式的文本"""
        header = f"🎬 {data.get('day', '当日')}全国电影票房榜 🎬"
        lines = [header, "=" * 30, ""]
        # 循环处理返回的电影数据，这里最多显示8部电影
        for i in range(1, 9):
            key = f"Top_{i}"
            movie = data.get(key)
            if not movie:
                break
            # 根据排名设置奖牌图标
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = "🎯"
            lines.append(f"{medal} No.{i} {movie.get('name', '未知')}")
            lines.append(f"├ 上映日期：{movie.get('release date', 'N/A')}")
            lines.append(f"├ 实时票房：{movie.get('Box Office Million', 'N/A')}")
            lines.append(f"├ 票房占比：{movie.get('Share of box office', 'N/A')}")
            lines.append(f"├ 排片占比：{movie.get('Row Films', 'N/A')}")
            lines.append(f"└ 排座占比：{movie.get('Row seats', 'N/A')}")
            lines.append("")  # 添加空行分隔各电影
        lines.append("=" * 30)
        lines.append(f"数据更新时间：{data.get('day', '未知时间')} ⏰")
        return "\n".join(lines)


    def _format_stock(self, data: Dict, show_num: int) -> str:
        """格式化股票数据"""
        stock = {
            "name": data.get("name", "未知股票"),
            "code": data.get("secid", "000000"),
            "data": data.get("data", [])[:show_num]
        }

        lines = [
            f"📊 {stock['name']} ({stock['code']}) 近期数据",
            f"📈 显示最近{len(stock['data'])}个交易日记录",
            "="*40
        ]

        for item in stock["data"]:
            lines.extend([
                f"📅 {item.get('time', '未知日期')}",
                f"▪️ 开盘：{item.get('opening', 'N/A')}",
                f"▪️ 收盘：{item.get('closing', 'N/A')}",
                f"▪️ 最高/最低：{item.get('highest', 'N/A')}/{item.get('lowest', 'N/A')}",
                f"▪️ 涨跌：{item.get('inorde', 'N/A')} ({item.get('inorde_amount', 'N/A')})",
                f"▪️ 成交量：{item.get('trading_volume', 'N/A')}",
                "-"*40
            ])

        lines.extend([
            "💡 高级功能支持：",
            "1. 输入完整代码查看更多数据（例：股票 300033 15）",
            "2. 输入'分析 股票代码'获取AI解读（功能开发中）",
            "="*40,
            "数据来源：PearkTrue Stock API"
        ])
        return "\n".join(lines)

    def _send_reply(self, e_context, msg: str):
        """发送回复"""
        e_context["reply"] = Reply(ReplyType.TEXT, msg)
        e_context.action = EventAction.BREAK_PASS

    def get_help_text(self, **kwargs):
        return """💼 金融数据查询插件
                        
【票房查询】
输入"票房"获取实时电影票房排行榜

【股票查询】
A股查询：股票 代码
查询中国A股市场：股票 300033

美股查询：美股 代码
查询美股市场股票：美股 AAPL

A股多日查询：股票 代码 数量
示例：股票 600519 10

【注意事项】
1. 股票代码需请确保输入正确的股票代码。对于中国A股市场，股票代码通常为6位数字；\n对于美股市场，股票代码通常为3-4个字母
2. A股数量参数范围1-50
3. 数据仅供参考，投资需谨慎

📌 数据更新频率：每30分钟刷新一次
"""
