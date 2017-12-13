'''
Created on 2017年12月13日

@author: 3xtrees
'''


from sqlalchemy import Column, String, Integer, Float, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import gevent

# 创建对象的基类:
Base = declarative_base()

# 定义涨停跳空对象


class ZZTK(Base):
    # 表的名字:
    __tablename__ = 'zztk'

    # 表的结构:
    ID = Column(Integer, primary_key=True)
    selected_date = Column(String(20))
    selected_code = Column(String(20))
    buy_date = Column(String(20))
    buy_price = Column(Float)
    sell_date = Column(String(20))
    sell_price = Column(Float)
    shares = Column(Integer)


engine = create_engine(
    'mysql+pymysql://root:root@localhost:3306/micro?charset=utf8')  # 用sqlalchemy创建mysql引擎

# 创建DBSession类型，以及session会话
DBSession = sessionmaker(bind=engine)
session = DBSession()

# 插入记录
zztk = ZZTK(selected_date='test', selected_code='test', buy_date='test',
            buy_price=10, sell_date='test', sell_price=11, shares=100)
try:
    session.add(zztk)
    session.commit()
except gevent.Timeout:
    session.invalidate()
    raise
except:
    session.rollback()
    raise

# 条件查询和更改
hi = session.query(ZZTK).filter(ZZTK.ID == 1).all()
for h in hi:
    setattr(h, 'selected_code', 'updated')
    session.commit()

# 关闭Session和数据库引擎
session.close()
engine.dispose()
