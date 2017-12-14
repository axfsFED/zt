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
from sqlUtils import py


def list2strSequence(list_agr):
    list_str = [str(l) for l in list_agr]
    strSequence = list_str[0]
    for i in range(1, len(list_str)):
        strSequence += (',' + list_str[i])
    return strSequence

#=========================================================================
# 输入：日期和股票
# 返回：该股票当日是否满足选股条件
#=========================================================================


def is_selected(code, date):
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


def selectStocks(date):
    selected_Stocks = []

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
            if is_selected(code, date_str1):
                selected_Stocks.append(code)
        except(BaseException):
            print(BaseException)
            continue
    # 返回选股结果
    return selected_Stocks

#=========================================================================
# 按照100000的资金，计算每一只股票的持仓数量和成本（考虑交易佣金）
# 输入：日期，买入股票列表，每只股票额度
# 输出：dataFrame-代码+持仓数量+持仓成本
#=========================================================================


def buyAssign(date, to_buy_list, cash_per_stock):

    total_cost = 0
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
        cost_stock = shares * open_list[i]  # 股票成本
        calc_commissions = round(cost_stock * commission_rate_buy + 0.001, 2)
        cost_commissions = calc_commissions if calc_commissions > 5 else 5  # 交易佣金
        cost = cost_stock + cost_commissions  # 总成本
        total_cost += cost
        cost_price = round(cost / shares + 0.0001, 3)  # 一股成本价格
        shares_list.append(shares)
        cost_price_list.append(cost_price)
    to_buy_df = pd.DataFrame()
    to_buy_df['security_code'] = to_buy_list
    to_buy_df['shares'] = shares_list
    to_buy_df['cost_price'] = cost_price_list
    return to_buy_df, total_cost

 #=========================================================================
 # 输入：日期，调仓换股周期, wind接口
 # 输出：要平仓股票的dateframe，以及当前持仓
 #=========================================================================


def to_sell(date, preTday = w.tdaysoffset(-adjust_period, date_str1, "").Data[0][0], w):
    date_str1 = date.strftime("%Y-%m-%d")
    preTday = w.tdaysoffset(-adjust_period, date_str1, "").Data[0][0]
    to_sell_objects = py.session.query(py.ZZTK).filter(
        py.ZZTK.buy_date <= preTday, py.ZZTK.shares > 0).all()
    return to_sell_objects


 #=========================================================================
 # 输入：日期, wind接口,选股结果列表
 # 输出：当日要买入的股票列表
 #=========================================================================
def to_buy(date, selected_stocks, adjust_period, w):
    date_str1 = date.strftime("%Y-%m-%d")
    preTday = w.tdaysoffset(-adjust_period, date_str1, "").Data[0][0]
    lastTday = w.tdaysoffset(-1, date_str1, "").Data[0][0]
    to_buy_objects = py.session.query(py.ZZTK).filter(
        py.ZZTK.selected_date == lastTday, py.ZZTK.shares == 0).all()
    return to_sell_objects

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
    isOk = True
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
    to_sell_df_filtered = to_sell_df[to_sell_df['security_code'].isin(
        to_sell_list)]

#------------------------------------------------------------------------------ 以当日收盘价卖出股票
    to_sell_list = list(to_sell_df_filtered["security_code"])
    if len(to_sell_list) > 0:
        print("今日卖出股票")
        print(to_sell_list)
        to_sell_list_shares = list(to_sell_df_filtered["shares"])
        to_sell_list_shares = [-s for s in to_sell_list_shares]
        _wss = w.wss(to_sell_list, "close", "tradeDate=" +
                     date_str2 + ";priceAdj=F;cycle=D")
        if _wss.ErrorCode != 0 or _wss.Data[0][0] is None:
            print("b1")
            print(_wss.ErrorCode)
            isOk = False
            return isOk
        close_list = _wss.Data[0]
        print(list2strSequence(to_sell_list))
        print(list2strSequence(to_sell_list_shares))
        print(list2strSequence(close_list))
        _wupf = w.wupf(pmsName, date_str2, list2strSequence(to_sell_list), list2strSequence(to_sell_list_shares), list2strSequence(close_list),
                       "Direction=Long;Method=BuySell;CreditTrading=No;type=flow")
        if _wupf.ErrorCode != 0:
            print("b2")
            print(_wupf.ErrorCode)
            isOk = False
            return isOk
        # 扣除卖出费用(佣金和印花税)
        cost_of_sell = 0
        for i in range(0, len(to_sell_list)):
            cost_of_sell += sellCost(close_list[i], -to_sell_list_shares[i],
                                     commission_rate_sell, stamp_duty_rate)
        _wupf = w.wupf(pmsName, date_str2, "CNY", str(-cost_of_sell), "1",
                       "Direction=Short;Method=BuySell;CreditTrading=No;type=flow")
        if _wupf.ErrorCode != 0:
            print("b3")
            print(_wupf.ErrorCode)
            isOk = False
            return isOk
    #-----------------------------------------------------------------------------更新持仓数据库


#------------------------------------------------------------------------------ 以当日开盘价买入股票
    if len(to_buy_list) > 0:
        print("今日买入股票")
        print(to_buy_list)
        # 计算资金缺口，上传资金流水
        to_buy_df, total_cost = buyAssign(date, to_buy_list, cash_per_stock)
        to_buy_list = list(to_buy_df['security_code'])
        shares_list = list(to_buy_df['shares'])
        cost_price_list = list(to_buy_df['cost_price'])

        # 计算资金缺口
        current_cash = w.wpf(pmsName, "PMS.PortfolioDaily",
                             "startdate=" + date_str2 + ";enddate=" + date_str2 + ";reportcurrency=CNY;field=Cash").Data[0][0]  # 当前组合现金
        if current_cash < total_cost:  # 如果资金短缺,增加现金
            w.wupf(pmsName, date_str2, "CNY", str(total_cost - current_cash), "1",
                   "Direction=Short;Method=BuySell;CreditTrading=No;type=flow")
        # 上传交易流水数据
        w.wupf(pmsName, date_str2, list2strSequence(to_buy_list), list2strSequence(shares_list),
               list2strSequence(cost_price_list), "Direction=Long;Method=BuySell;CreditTrading=No;type=flow")
    #------------------------------------------------------------------------------ 更新持仓数据库
        df = pd.DataFrame(columns=['buy_date', 'selected_code', 'shares'])
        df['buy_date'] = [date_str1 for i in to_buy_list]
        df['selected_code'] = to_buy_list
        df['shares'] = shares_list
        df.to_sql('zztk_hold_his', py.engine, if_exists='append', index=False,
                  dtype={'date': String(20), 'selected_code': String(20)})  # 类型映射，增量入库
    return isOk


if __name__ == '__main__':
    pmsName = "test"  # 组合信息
    cash_per_stock = 100000  # 单只标的金额
    adjust_period = 5

    # 当前时间（每日下午4:20运行）
    now = datetime.datetime.now()
    date_str1 = now.strftime("%Y-%m-%d")
    date_str2 = now.strftime("%Y%m%d")

    w.start()  # 启动WIND
#------------------------------------------------------------------------------ step1.选股，写入MySQL(zztk_result选股结果表)
#     #pre_day = w.tdaysoffset(-1, now.strftime("%Y-%m-%d"), "").Data[0][0]
#     #date_str1 = pre_day.strftime("%Y-%m-%d")
#
#     #selected_codes = to_buy_list(pre_day)
#     selected_codes = ['001', '002']
#     print(selected_codes)
#     df = pd.DataFrame(columns=['selected_date', 'selected_code'])
#     df['selected_date'] = [date_str1 for i in selected_codes]
#     df['selected_code'] = selected_codes
#     df['shares'] = [0 for i in selected_codes]
#     df.to_sql('zztk', py.engine, if_exists='append', index=False,
#               dtype={'date': String(20), 'selected_code': String(20)})  # 类型映射，增量入库
#------------------------------------------------------------------------------ step2.当前持仓信息，以及满N日平仓(zztk_hold当前持仓表)列表
    to_sell_objects = to_sell(now, adjust_period, w)
    print(to_sell_objects[0].buy_date)
#------------------------------------------------------------------------------ step3.调整仓位
    isOk = True
#     to_buy_list = []
#     isOk = adjust_position(pmsName, now, to_buy_list, hold_list,
#                            to_sell_df, cash_per_stock)
#------------------------------------------------------------------------------ finally.关闭wind接口，输出信息
    w.stop()
    if not isOk:
        print("wrong!")
    else:
        print('Mission Complete!')

    # 关闭Session和数据库引擎
    py.session.close()
    py.engine.dispose()
