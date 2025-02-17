# DataRetrieval
DataRetrieval 是一款适用于 dify-on-wechat 项目的电影票房,股票查询插件，支持实时查询全网电影票房以及股票数据。

## 一. 主要功能
1. 实时票房：查询当日实时票房排行
2. A股和美股信息实时查询



## 二. 安装配置
1. 安装插件：`#installp https://github.com/sllt-wei/DataRetrieval.git`
2. config.json.template修改为config.json，把参数us_stock_api_token[申请地址：https://www.stockdata.org/documentation]以及智谱的zhipu_api_key
3. 重启项目并扫描插件：`#scanp`

## 三. 使用指令
- 发送"票房"：获取当日实时票房排行榜
- A股查询：股票 代码 
- 查询中国A股市场：股票 300033

- 美股查询：美股 代码
- 查询美股市场股票：美股 AAPL

- A股多日查询：股票 代码 数量
- 示例：股票 600519 10

