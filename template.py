'''
跳空涨停股票筛选和自动调仓换股
输入：wind平台数据
输出：选股结果-->mysql数据库，调仓结果-->wind组合管理
执行逻辑：
每日下午4:30执行
step1.选出当日满足条件股票
step2.将前一日选出股票按照当日开盘价建仓
step3.持仓满五天的进行平仓
history
v0.0-20171123, 主程序架构
v0.1-20171207, 选股结果入库，次日建仓，定期调仓（平）
'''
# 导入函数库
from pylab import *
mpl.rcParams['font.sans-serif'] = ['SimHei']  # 中文乱码的问题
from WindPy import *  # 导入wind接口
import datetime
import time
import calendar
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy
import math
from sqlalchemy import create_engine  # 导入数据库接口
from sqlalchemy.types import String
from string import Template


def backtestSelectStock(beginDay, endDay, period_adjust, period_strategy, hold_stock_num):
    # 根据起始日期和终止日期计算出每个周期的选股列表
    strPeriodOption = ''

    if period_adjust == 'W':
        strPeriodOption = 'Period=W'
    elif period_adjust == 'Y':
        strPeriodOption = 'Period=Y'
    elif period_adjust == 'D':
        strPeriodOption = 'Period=TD'
    else:
        strPeriodOption = 'Period=M'
    w_tdays_data = w.tdays(beginDay, endDay, strPeriodOption)
    dates = w_tdays_data.Times  # datetime.date

    adjust_dates = [d.strftime('%Y%m%d') for d in dates]
    SelectStocks = []  # 创建一个空的dataframe

    for d in dates:
        code_list = SelectStockStrategy(d, period_strategy, hold_stock_num)
        SelectStocks.append(code_list)
    return adjust_dates, SelectStocks


def list2strSequence(list_agr):
    list_str = [str(l) for l in list_agr]
    strSequence = list_str[0]
    for i in range(1, len(list_str)):
        strSequence += (',' + list_str[i])
    return strSequence


def backtest(adjust_days, SelectStocks, pmsName, moneyAmount):
    # 使用PMS做回测
    #MoenyAssignStock: 资金配比function
    #pmsName:    PMS组合名称
    # moneyAmount:总共资金

    # 先清除PMS内容

    # 按等权回测，每一个调仓日调整持股仓位，k为调仓换股日
    for k in range(0, len(adjust_days)):
        if len(SelectStocks[k]) == 0:
            continue
        # 显示调仓日期
        adjust_day = adjust_days[k]
        print(adjust_day)

        strSelectStockCodes = SelectStocks[k]

        _wss = w.wss(strSelectStockCodes, 'vwap', 'tradeDate=' +
                     adjust_day, 'cycle=D', 'priceAdj=F')
        averagePriceData = _wss.Data[0]

        # 获取资金配比
        curAccountMoney = 0
        if k == 0:  # 初始建仓，直接按原始资金配股
            curAccountMoney = moneyAmount
        else:
            # 先获取当前总资产(市值+当前现金)，然后按照总资金配比
            time.sleep(3)  # Pause for 3 seconds
            _wpf = w.wpf(pmsName, "PMS.PortfolioDaily", "startdate=" + adjust_day + ";enddate=" +
                         adjust_day + ";reportcurrency=CNY;field=Report_Currency,Total_Asset")
            print(_wpf.ErrorCode)
            print(_wpf.Data)
            curAccountMoney = _wpf.Data[1][0]

        # 计算每只股票的持仓手数，以及剩余现金
        remainderMoney = curAccountMoney
        board_lot = []
        averageMoneyAmount = curAccountMoney / len(strSelectStockCodes)
        for p in averagePriceData:
            board_lot_single = int(floor(averageMoneyAmount / p / 100))
            board_lot.append(board_lot_single)
            remainderMoney = remainderMoney - board_lot_single * 100 * p

        stocks_num = [lot * 100 for lot in board_lot]
        # 计算剩余资金
        strSelectStockCodes.append("CNY")
        stocks_num.append(remainderMoney)
        averagePriceData.append(1)

        print(list2strSequence(strSelectStockCodes))
        print(list2strSequence(stocks_num))
        print(list2strSequence(averagePriceData))

        time.sleep(3)  # Pause for 3 seconds
        # 上传持仓信息，之前的持仓失效
        _debug = w.wupf(pmsName, adjust_day, list2strSequence(strSelectStockCodes), list2strSequence(
            stocks_num), list2strSequence(averagePriceData), "Direction=Long;CreditTrading=No;HedgeType=Spec;")
        print(_debug.ErrorCode)


def SelectStockStrategy(d, period_strategy, hold_stock_num):
    # 选取股票策略
    # 返回d日选出的股票列表CodeList(code)
    strCurDay = d.strftime('%Y-%m-%d')

    # 前一个交易日
    w_tdays_data = w.tdaysoffset(-1, strCurDay)
    strPreDay = w_tdays_data.Times[0].strftime('%Y-%m-%d')

    strPeriodBeginDay = ''
    if period_strategy == 'W':
        strPeriodBeginDay = 'ED-1W'
    elif period_strategy == 'Y':
        strPeriodBeginDay = 'ED-1Y'
    elif period_strategy == 'D':
        strPeriodBeginDay = 'ED-1TD'
    else:
        strPeriodBeginDay = 'ED-1M'

    # 取沪深300的成分及权重
    strOption = 'date=' + strCurDay + ';windcode=000300.SH'
    HS300Stock = w.wset('IndexConstituent', strOption)
    strHS300Codes = HS300Stock.Data[1]
    HS300StockData = pd.DataFrame(strHS300Codes, columns=['codes'])

    # 取近一个月的涨跌幅
    wss_data = w.wss(strHS300Codes, 'chg_per,pct_chg_per',
                     'startDate=' + strPeriodBeginDay, 'endDate=' + strCurDay)
    HS300StockData['pct_chg_per'] = wss_data.Data[1]
    # 取昨天是否涨跌停
    wss_data = w.wss(strHS300Codes, 'maxupordown', 'tradeDate=' + strPreDay)
    HS300StockData['preMaxupordown_data'] = wss_data.Data[0]

    # 取今天停牌的股票
    stopStock = w.wset('TradeSuspend', 'startdate=' +
                       strCurDay, 'enddate=' + strCurDay)
    stopStockList = stopStock.Data[1]

    # 按涨跌幅从小到大排序
    sortHS300StockData = HS300StockData.sort_values(
        by='pct_chg_per', axis=0, ascending=True)

    print(sortHS300StockData['pct_chg_per'])

    # 取跌幅最大的n支股票（过滤掉停牌、昨天涨停的）
    code_list = []
    count = 1
    maxupStatus = 0
    for i in sortHS300StockData.index:
        maxupStatus = sortHS300StockData['preMaxupordown_data'][i]
        if 1 == maxupStatus:
            continue
        elif sortHS300StockData['codes'][i] in stopStockList:
            continue
        else:
            code_list.append(sortHS300StockData['codes'][i])
            count = count + 1
            print(sortHS300StockData['pct_chg_per'][i])
            if (count > hold_stock_num):
                break
    return code_list


#=========================================================================
# 输入：日期和股票
# 返回：该股票当日是否满足选股条件
#=========================================================================
def is_to_buy(code, date):
    '''
    1、10天内出现过涨停（剔除一字涨停和上市未满1年的次新股），并且随后股价最低价一直高于涨停价；ever_maxup and con1
    2、涨停第二天跳空高开，并且全天最低价不低于之前的涨停价，涨停第二天成交量显著放大；con2
    3、股价缩量到涨停第二天成交的三分之一或以下，换手率少于涨停第二天的一半，则第二天开盘买入；con3
    '''
    con2_agr = [0.5]
    con3_arg = [1 / 3, 1 / 2]
    to_buy = False
    _wsd = w.wsd(code, "open,close,low,high,maxupordown,volume,free_turn",
                 "ED-10TD", date, "PriceAdj=F")
    open_price = _wsd.Data[0]
    close = _wsd.Data[1]
    low = _wsd.Data[2]
    high = _wsd.Data[3]
    maxupordown = _wsd.Data[4]
    volume = _wsd.Data[5]
    free_turn = _wsd.Data[6]
    ever_maxup = False
    if maxupordown.count(1) > 0:
        ever_maxup = True
    if ever_maxup:
        maxup_mark = maxupordown.index(1)  # 第一个涨停的索引位置
        while maxup_mark < len(maxupordown):
            if low[maxup_mark] < high[maxup_mark]:  # 不是一字涨停
                break
            else:
                maxup_mark = maxupordown[maxup_mark +
                                         1:-1].index(1) + maxup_mark + 1
        if maxup_mark == len(maxupordown) - 1:  # 如果是当日涨停，返回false
            return to_buy
        con1 = True
        for i in range(maxup_mark + 1, len(low)):
            if low[i] < close[maxup_mark]:
                con1 = False
        con2 = False
        if open_price[maxup_mark + 1] > high[maxup_mark] and low[maxup_mark + 1] >= close[maxup_mark] and volume[maxup_mark + 1] > (1 + con2_agr[0]) * volume[maxup_mark]:
            con2 = True
        con3 = False
        if volume[-1] <= volume[maxup_mark + 1] * con3_arg[0] and free_turn[-1] < free_turn[maxup_mark + 1] * con3_arg[1]:
            con3 = True
        if con1 and con2 and con3:
            to_buy = True
    return to_buy

#=========================================================================
# 输入：日期
# 返回：当日选股列表
#=========================================================================


def to_buy_list(date):
    to_buy_list = []

    date_str1 = date.strftime("%Y-%m-%d")
    date_str2 = date.strftime("%Y%m%d")

    # 获取当前所有股票列表
    target_list = w.wset("sectorconstituent", "date=" +
                         date_str1 + ";sectorid=a001010100000000").Data[1]  # 当日标的成分
    ipo_listdays_list = w.wss(target_list, "ipo_listdays",
                              "tradeDate=" + date_str2).Data[0]  # 获取当天标的成分的上市天数（自然日）
    ipo_list_one_year = [True if (
        ipo_days > 365) else False for ipo_days in ipo_listdays_list]  # 判断标的成分是否上市满一年

    total_num = len(target_list)
    for i in range(0, total_num):
        if not ipo_list_one_year[i]:  # 如果上市不满一年
            continue
        code = target_list[i]
        print("%d/%d" % (i + 1, total_num))
        try:
            if is_to_buy(code, date_str1):
                to_buy_list.append(code)
        except(BaseException):
            print(BaseException)
            continue
    # 返回选股结果
    return to_buy_list

#=========================================================================
# 按照100000的资金，计算每一只股票的持仓数量和成本（考虑交易佣金）
# 输入：日期，买入股票列表，每只股票额度
# 输出：dataFrame-代码+持仓数量+持仓成本
#=========================================================================


def buyAssign(date, to_buy_list, cash_per_stock):

    commission_rate_buy = 0.0003  # 买入佣金比例
    date_str2 = date.strftime("%Y%m%d")
    # 获取当天被选股票列表的开盘价
    open_list = w.wss(to_buy_list, "open", "tradeDate=" +
                      date_str2 + ";priceAdj=F;cycle=D").Data[0]
    cost_price_list = []
    shares_list = []
    # 计算每一只被选股票的持有数量和成本
    for i in range(0, len(to_buy_list)):
        shares = math.floor(cash_per_stock / open_list[i] / 100) * 100
        cost_stock = shares * open_list[i]
        calc_commissions = round(cost_stock * commission_rate_buy + 0.001, 2)
        cost_commissions = calc_commissions if calc_commissions > 5 else 5
        cost_price = round(
            (cost_stock + cost_commissions) / shares + 0.0001, 3)
        shares_list.append(shares)
        cost_price_list.append(cost_price)
    to_buy_df = pd.DataFrame()
    to_buy_df['security_code'] = to_buy_list
    to_buy_df['shares'] = shares_list
    to_buy_df['cost_price'] = cost_price_list
    return to_buy_df

 #=========================================================================
 # 输入：日期，数据库引
 # 输出：平仓列表
 #=========================================================================


def to_sell_df(date, engine):
    date_str1 = date.strftime("%Y-%m-%d")
    date_str2 = date.strftime("%Y%m%d")
    adjust_period = 5
    _wpf = w.wpf(pmsName, "PMS.HoldingDaily", "tradedate=" +
                 date_str2 + ";reportcurrency=CNY")
    long_positions = _wpf.Data[0]  # pms获取当前持仓信息

    to_sell_df = pd.DataFrame(
        columns=['buy_date', 'security_code', 'shares'])  # 当日卖出股票df, 建仓日期+代码+数量
    query_sql = """
      select * from $arg1
      """
    query_sql = Template(query_sql)  # template方法
    df = pd.read_sql_query(query_sql .substitute(
        arg1='zztk_hold'), engine)  # 配合pandas的方法读取数据库值，数据库获取当日持仓信息

    buy_date = list(df['buy_date'])
    security_code = list(df['security_code'])

    for i in range(0, len(buy_date)):
        tradeDays = w.tdayscount(buy_date[i], date_str1, "").Data[0][0]
        if tradeDays == adjust_period:
            to_sell_df = to_sell_df.append(df.iloc[i])
    return to_sell_df, security_code

#=========================================================================
# 计算单只股票卖出的佣金和印花税
# 返回总卖出总费用
#=========================================================================


def sellCost(price, shares, commission_rate_sell, stamp_duty_rate):
    calc_commissions = round(price * shares * commission_rate_sell + 0.001, 2)
    cost_commissions = calc_commissions if calc_commissions > 5 else 5
    cost_stamp_duty = price * shares * stamp_duty_rate
    return cost_commissions + cost_stamp_duty


def adjust_position(pmsName, date, to_buy_list, hold_list, to_sell_df, cash_per_stock):
    commission_rate_sell = 0.0003  # 卖出佣金
    stamp_duty_rate = 0.001  # 印花税
    date_str1 = date.strftime("%Y-%m-%d")
    date_str2 = date.strftime("%Y%m%d")

    to_sell_list = list(to_sell_df['security_code'])
    # 求to_sell_list和to_buy_list的交集，to_buy_list和to_sell_list分别去除共同的部分
    intersection = list(set(to_buy_list).intersection(set(to_sell_list)))
    to_buy_list = list(set(to_buy_list).difference(set(intersection)))
    to_buy_list = list(set(to_buy_list).difference(
        set(hold_list)))  # to_buy_list去除hold_list中已经有的部分

    to_sell_list = list(set(to_sell_list).difference(set(intersection)))
    to_sell_df[to_sell_df['security_code'].isin(to_buy_list)]

#------------------------------------------------------------------------------ 以当日收盘价卖出股票
    to_sell_list = list((to_sell_df["security_code"]))
    to_sell_list_shares = list(to_sell_df["shares"])
    to_sell_list_shares = [-s for s in to_sell_list_shares]
    close_list = w.wss(to_sell_list, "close", "tradeDate=" +
                       date_str2 + ";priceAdj=F;cycle=D").Data[0]
    w.wupf(pmsName, date_str2, list2strSequence(to_sell_list), list2strSequence(to_sell_list_shares), list2strSequence(close_list),
           "Direction=Long,Long;Method=BuySell,BuySell;CreditTrading=No,No;type=flow")
    # 扣除卖出费用(佣金和印花税)
    cost_of_sell = 0
    for i in range(0, len(to_sell_list)):
        cost_of_sell += sellCost(close_list[i], -to_sell_list_shares[i],
                                 commission_rate_sell, stamp_duty_rate)
    w.wupf(pmsName, date_str2, "CNY", str(-cost_of_sell), "1",
           "Direction=Short;Method=BuySell;CreditTrading=No;type=flow")
    
#------------------------------------------------------------------------------ 以当日开盘价买入股票
    # 计算资金缺口，上传资金流水
    to_buy_df = buyAssign(date, to_buy_list, cash_per_stock)
    to_buy_list = to_buy_df['to_buy_list']
    shares_list = to_buy_df['shares_list']
    cost_price_list = to_buy_df['cost_price_list']
    stock_num = len(to_buy_list)

    w.wupf(pmsName, date_str2, "CNY", str(stock_num *
                                          cash_per_stock), "1", "Direction=Long;CreditTrading=No;HedgeType=Spec;")
    # 上传交易流水数据
    w.wupf(pmsName, date_str2, list2strSequence(to_buy_list), list2strSequence(shares_list),
           list2strSequence(cost_price_list), "Direction=Long;Method=BuySell;CreditTrading=No;type=flow")
#------------------------------------------------------------------------------ 更新持仓数据库


if __name__ == '__main__':
    # 组合信息
    pmsName = "test"
    cash_per_stock = 100000  # 单只标的金额

    # 当前时间（每日下午4:30运行）
    now = datetime.datetime.now()
    date_str1 = now.strftime("%Y-%m-%d")
    date_str2 = now.strftime("%Y%m%d")

    w.start()  # 启动WIND
    engine = create_engine(
        'mysql+pymysql://root:root@localhost:3306/micro?charset=utf8')  # 用sqlalchemy创建mysql引擎
#------------------------------------------------------------------------------ step1.选股，写入MySQL(zztk_result选股结果表)
#     #pre_day = w.tdaysoffset(-1, now.strftime("%Y-%m-%d"), "").Data[0][0]
#     to_buy_list = to_buy_list(now)
#     print(to_buy_list)
#     df = pd.DataFrame(columns=['date', 'selected_code'])
#     df['date'] = [date_str1 for i in to_buy_list]
#     df['selected_code'] = to_buy_list
#     df.to_sql('zztk_result', engine, if_exists='append', index=False,
#               dtype={'date': String(20), 'selected_code': String(20)})  # 类型映射，增量入库
#------------------------------------------------------------------------------ step2.当前持仓信息，以及满N日平仓(zztk_hold当前持仓表)列表
    to_sell_df, hold_list = to_sell_df(now, engine)
    print(hold_list)
    print(to_sell_df)
#------------------------------------------------------------------------------ step3.调整仓位
#     adjust_position(pmsName, now, to_buy_list, hold_list, to_sell_df, cash_per_stock)
#------------------------------------------------------------------------------ finally.关闭wind接口，输出信息
    w.stop()
    print('Mission Complete!')
