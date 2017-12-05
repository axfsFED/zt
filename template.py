'''
输入：wind平台数据
输出：无，wind组合管理
history
v0.0-20171123, 主程序架构
'''
# 导入函数库
from pylab import *
mpl.rcParams['font.sans-serif'] = ['SimHei'] # 中文乱码的问题
from WindPy import * # 导入wind接口
import datetime,time,calendar
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy
import math

def backtestSelectStock(beginDay, endDay, period_adjust, period_strategy, hold_stock_num):
    #根据起始日期和终止日期计算出每个周期的选股列表
    strPeriodOption = ''

    if period_adjust == 'W':
        strPeriodOption = 'Period=W'
    elif period_adjust == 'Y':
        strPeriodOption = 'Period=Y'
    elif period_adjust == 'D':
        strPeriodOption = 'Period=TD'
    else:
        strPeriodOption = 'Period=M'
    w_tdays_data=w.tdays(beginDay,endDay,strPeriodOption)
    dates = w_tdays_data.Times #datetime.date

    adjust_dates = [d.strftime('%Y%m%d') for d in dates]
    SelectStocks = [] #创建一个空的dataframe

    for d in dates:
        code_list = SelectStockStrategy(d, period_strategy, hold_stock_num)
        SelectStocks.append(code_list)
    return adjust_dates, SelectStocks

def list2strSequence(list_agr):
    list_str = [str(l) for l in list_agr]
    strSequence = list_str[0]
    for i in range(1,len(list_str)):
        strSequence += (','+list_str[i])
    return strSequence

def backtest(adjust_days, SelectStocks, pmsName, moneyAmount):
    #使用PMS做回测
    #MoenyAssignStock: 资金配比function
    #pmsName:    PMS组合名称
    #moneyAmount:总共资金

    #先清除PMS内容
    
    #按等权回测，每一个调仓日调整持股仓位，k为调仓换股日
    for k in range(0, len(adjust_days)):
        if len(SelectStocks[k]) == 0:
            continue
        #显示调仓日期
        adjust_day = adjust_days[k]
        print(adjust_day)
        
        strSelectStockCodes = SelectStocks[k]
        
        _wss = w.wss(strSelectStockCodes,'vwap', 'tradeDate='+adjust_day, 'cycle=D','priceAdj=F')
        averagePriceData = _wss.Data[0]
        
        #获取资金配比
        curAccountMoney = 0
        if k==0: #初始建仓，直接按原始资金配股
            curAccountMoney = moneyAmount
        else:
            #先获取当前总资产(市值+当前现金)，然后按照总资金配比
            time.sleep(3) # Pause for 3 seconds
            _wpf = w.wpf(pmsName, "PMS.PortfolioDaily","startdate="+adjust_day+";enddate="+adjust_day+";reportcurrency=CNY;field=Report_Currency,Total_Asset")
            print(_wpf.ErrorCode)
            print(_wpf.Data)
            curAccountMoney = _wpf.Data[1][0]
        
        # 计算每只股票的持仓手数，以及剩余现金
        remainderMoney = curAccountMoney
        board_lot = []
        averageMoneyAmount = curAccountMoney / len(strSelectStockCodes)
        for p in averagePriceData:
            board_lot_single = int(floor(averageMoneyAmount/p/100))
            board_lot.append(board_lot_single)
            remainderMoney = remainderMoney - board_lot_single*100*p
        
        stocks_num = [lot*100 for lot in board_lot]
        #计算剩余资金
        strSelectStockCodes.append("CNY")
        stocks_num.append(remainderMoney)
        averagePriceData.append(1)

        print(list2strSequence(strSelectStockCodes))
        print(list2strSequence(stocks_num))
        print(list2strSequence(averagePriceData))
        
        time.sleep(3) # Pause for 3 seconds
        # 上传持仓信息，之前的持仓失效
        _debug = w.wupf(pmsName, adjust_day, list2strSequence(strSelectStockCodes), list2strSequence(stocks_num), list2strSequence(averagePriceData),"Direction=Long;CreditTrading=No;HedgeType=Spec;")
        print(_debug.ErrorCode)

def SelectStockStrategy(d, period_strategy, hold_stock_num):
    #选取股票策略
    #返回d日选出的股票列表CodeList(code)
    strCurDay = d.strftime('%Y-%m-%d')

    #前一个交易日
    w_tdays_data = w.tdaysoffset(-1,strCurDay)
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

    #取沪深300的成分及权重
    strOption = 'date=' + strCurDay + ';windcode=000300.SH'
    HS300Stock=w.wset('IndexConstituent',strOption)
    strHS300Codes = HS300Stock.Data[1]
    HS300StockData = pd.DataFrame(strHS300Codes, columns = ['codes'])

    #取近一个月的涨跌幅
    wss_data=w.wss(strHS300Codes,'chg_per,pct_chg_per', 'startDate=' + strPeriodBeginDay, 'endDate=' + strCurDay)
    HS300StockData['pct_chg_per'] = wss_data.Data[1]
    #取昨天是否涨跌停
    wss_data=w.wss(strHS300Codes,'maxupordown', 'tradeDate=' + strPreDay)
    HS300StockData['preMaxupordown_data'] = wss_data.Data[0]

    #取今天停牌的股票
    stopStock=w.wset('TradeSuspend', 'startdate=' + strCurDay, 'enddate=' + strCurDay)
    stopStockList = stopStock.Data[1]

    #按涨跌幅从小到大排序
    sortHS300StockData = HS300StockData.sort_values(by = 'pct_chg_per',axis = 0,ascending = True)

    print(sortHS300StockData['pct_chg_per'])

    #取跌幅最大的n支股票（过滤掉停牌、昨天涨停的）
    code_list = []
    count = 1
    maxupStatus=0
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

def is_to_buy(code, date):
    '''
    1、10天内出现过涨停（剔除一字涨停和上市未满1年的次新股），并且随后股价最低价一直高于涨停价；ever_maxup and con1
    2、涨停第二天跳空高开，并且全天最低价不低于之前的涨停价，涨停第二天成交量显著放大；con2
    3、股价缩量到涨停第二天成交的三分之一或以下，换手率少于涨停第二天的一半，则第二天开盘买入；con3
    '''
    con2_agr = [0.5]
    con3_arg = [1/3, 1/2]
    to_buy = False
    _wsd = w.wsd(code, "open,close,low,high,maxupordown,volume,free_turn", "ED-10TD", date, "PriceAdj=F")
    open_price =  _wsd.Data[0]
    close = _wsd.Data[1]
    low =  _wsd.Data[2]
    high =  _wsd.Data[3]
    maxupordown = _wsd.Data[4]
    volume = _wsd.Data[5]
    free_turn = _wsd.Data[6]
    ever_maxup = False
    if maxupordown.count(1) > 0:
        ever_maxup = True
    if ever_maxup:
        maxup_mark = maxupordown.index(1) #第一个涨停的索引位置
        while maxup_mark < len(maxupordown):
            if low[maxup_mark] < high[maxup_mark]:#不是一字涨停
                break
            else:
                maxup_mark = maxupordown[maxup_mark+1:-1].index(1)+maxup_mark+1
        if maxup_mark == len(maxupordown)-1: #如果是当日涨停，返回false
            return to_buy
        con1 = True
        for i in range(maxup_mark+1, len(low)):
            if low[i] < close[maxup_mark]:
                con1 = False
        con2 = False
        if open_price[maxup_mark+1] > high[maxup_mark] and low[maxup_mark+1] >= close[maxup_mark] and volume[maxup_mark+1]>(1+con2_agr[0])*volume[maxup_mark]:
            con2 = True
        con3 = False
        if volume[-1]<=volume[maxup_mark+1]*con3_arg[0] and free_turn[-1]<free_turn[maxup_mark+1]*con3_arg[1]:
            con3 = True
        if con1 and con2 and con3:
            to_buy = True
    return to_buy
    
def adjust_position(date, to_buy_list, cash_per_stock):
    #首先获取当前持仓，如果有的话就从to_buy_list剔除
    
    stock_num = len(to_buy_list)
    #上传现金
    w.wupf(pmsName, date.strftime("%Y%m%d"), "CNY", str(stock_num*cash_per_stock), "1","Direction=Long;CreditTrading=No;HedgeType=Spec;")
    
    #获取当天被选股票列表的开盘价
    open_list = w.wss(to_buy_list, "open","tradeDate="+date.strftime("%Y%m%d")+";priceAdj=F;cycle=D").Data[0]
    cost_price_list = []
    hold_num_list = []
    #计算每一只被选股票的持有数量和成本
    for i in range(0,len(to_buy_list)):
        hold_num = math.floor(cash_per_stock/open_list[i]/100)*100
        cost_stock = hold_num*open_list[i]
        calc_commissions = round(cost_stock*commission_rate_buy+0.001,2)
        cost_commissions = calc_commissions if calc_commissions>5 else 5
        cost_price = round((cost_stock+cost_commissions)/hold_num+0.0001, 3)
        hold_num_list.append(hold_num)
        cost_price_list.append(cost_price)
    #上传交易流水数据
    w.wupf(pmsName, date.strftime("%Y%m%d"), list2strSequence(to_buy_list), list2strSequence(hold_num_list), list2strSequence(cost_price_list),"Direction=Long;Method=BuySell;CreditTrading=No;type=flow")
    
if __name__ == '__main__':
    #组合信息
    pmsName = "0"
    cash_per_stock = 100000
    commission_rate_buy = 0.0003
    commission_rate_sell = 0.0003
    #启动WIND
    w.start()
    #基准指数
    index = '000001.SH'
    #当前时间
    now = datetime.datetime.now()
    #上一个交易日
    pre_tradeday = w.tdaysoffset(-1, now.strftime("%Y-%m-%d"), "").Data[0][0]
    
    date_str1 = pre_tradeday.strftime("%Y-%m-%d")
    date_str2 = pre_tradeday.strftime("%Y%m%d")
    #获取当前所有股票列表
    target_list = w.wset("sectorconstituent","date="+date_str1+";sectorid=a001010100000000").Data[1] #当日标的成分
    ipo_listdays_list = w.wss(target_list, "ipo_listdays","tradeDate="+date_str2).Data[0] # 获取当天标的成分的上市天数（自然日）
    ipo_list_one_year = [True if (ipo_days > 365) else False for ipo_days in ipo_listdays_list] #判断标的成分是否上市满一年
    
    to_buy_list = []
    for i in range(0,len(target_list)):
        if not ipo_list_one_year[i]: #如果上市不满一年
            continue
        code = target_list[i]
        #获取时间序列数据，插入数据库
        
        print(code)
        try:
            if is_to_buy(code, date_str1):
                to_buy_list.append(code)
        except(BaseException):
            print(BaseException)
            continue
    print(to_buy_list)
    '''
    #回测时间
    beginDay = (now - datetime.timedelta(days=100)).strftime("%Y-%m-%d")
    endDay = (now - datetime.timedelta(days=10)).strftime("%Y-%m-%d")
    #调仓换股周期
    period_adjust = 'W'
    #指标统计周期
    period_strategy = 'M'
    #回测资金
    moneyAmount = 1000000
    #回测组合名称
    pmsName = 'testPython'
    #持仓个数
    hold_stock_num = 30
    #重置组合
    w.wupf(pmsName, "", "", "", "","reset=true")
    #选股
    adjust_days, SelectStocks = backtestSelectStock(beginDay, endDay, period_adjust, period_strategy, hold_stock_num)
    #回测
    backtest(adjust_days, SelectStocks, pmsName, moneyAmount)
    '''
    print('Mission Complete!')