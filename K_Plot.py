#!/use/bin/dev python
# -*- coding: utf-8 -*-
""" 画K好看的线图 """
# 依赖mpl_finance qbstyles
import math
import traceback
from qbstyles import mpl_style
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.widgets import Cursor
from mpl_finance import candlestick_ohlc

# 使用qbstyles风格, 也可以换成其他的
mpl_style(dark=True)

class K_Plot():

    def __init__(self, ax_num=1):
        """ 初始化 """
        # ************ 系统变量 ************
        # 事发第一次触发回调模式不触发逻辑,这是由于用户最大化会触发回调
        self.show_k_info_motion_is_first_flag = True
        self.show_position_price_motion_is_first_flag = True

        # ************ 作图变量 ************
        # 开启动态作图
        plt.ion()

        # 子图个数
        self.ax_num = ax_num

        if self.ax_num not in (1, 4):
            # 暂时只支持一个子图, 或者上下4个子图
            print("The ax_num must be 1 or 2 or 4!")
            return

        # 创建画布
        if self.ax_num == 1:
            self.fig, ax = plt.subplots(figsize=(18, 10), ncols=1, nrows=1)
            self.ax_list = [ax]
        elif self.ax_num == 4:
            self.fig, self.ax_list = plt.subplots(figsize=(10, 17), ncols=1, nrows=4)

        # 设置窗口标题
        self.fig.canvas.set_window_title('K_Plot')

        # ax 变量字典,用以保存各个ax中的变量信息
        self.ax_variables_dict = dict()
        for ax in self.ax_list:
            self.ax_variables_dict[ax] = dict()

        # 显示鼠标跟随十字线,这里需要创建变量名不同的变量,不然只会显示一个
        self._cursor_list = list()

        # 调整子图间距, 百分比
        plt.subplots_adjust(top=0.95, bottom=0.02, hspace=0.25)

        # 创建ax列表生成器
        def generate_ax_list():
            while True:
                for ax in self.ax_list:
                    yield ax

        self._get_next_ax_gen = generate_ax_list()

        # 绑定回调
        self.band_action()

    def plot_k(self, df, ax='Default'):
        """ 在ax子图上画k线 """
        if ax == 'Default':
            # 如果用户未指定,就使用生成器生成一个
            ax = next(self._get_next_ax_gen)

        # 先清空ax,可以重复的画图
        ax.cla()

        # 构造candlestick_ohlc需求的数据列表
        quotes = []
        for i in range(len(df)):
            quotes.append([i, df.iloc[i].open, df.iloc[i].high, df.iloc[i].low, df.iloc[i].close])

        # 横轴名称, 取了数据时间序列
        index = df.index

        # 最新时间
        last_eob = index[-1]

        # 合约代码
        symbol = df.symbol[0].decode()
        # 合约周期
        frequency = df.frequency[0]
        # k线根数
        k_num = len(df)

        # 设置表标题
        ax.set_title(symbol, fontdict = {'size': 16})

        # 横轴内容提取函数
        def format_date(x, pos=None):
            if x<0 or x>len(index)-1:
                return ''
            return index[int(x)]

        # 显示表格
        ax.grid(True)
        # 每个格子里面显示7跟k线
        ax.xaxis.set_major_locator(ticker.MultipleLocator(math.floor(k_num/6)))
        # 设置横坐标显示内容提取函数
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(format_date))

        # 在ax里画k线图
        #  candlestick_ohlc_list = candlestick_ohlc(ax, quotes, colordown='#00F0F0', colorup='#ff1717', width=0.4)
        candlestick_ohlc(ax, quotes, colordown='#00F0F0', colorup='#ff1717', width=0.4)

        # 添加十字线,这里必须保存这个变量,或者用不同的变量名,不然子图只会显示一个十字线
        self._cursor_list.append(Cursor(ax, useblit=True, color='w', linewidth=1))

        # 使用transform来指定text在图片中的相对位置
        # 显示在左上角
        # 显示k线根数
        #  k_num_ax_text = ax.text(0.02, 0.93, 'Num: {0}'.format(k_num), transform=ax.transAxes, fontdict = {'size': 10, 'color': 'w'})
        k_num_ax_text = ax.text(0.86, 1.06, 'Num: {0}'.format(k_num), transform=ax.transAxes, fontdict = {'size': 10, 'color': 'w'})
        # 显示k线周期
        frequency_ax_text = ax.text(0.86, 1.02, 'frequency: {0}'.format(frequency), transform=ax.transAxes, fontdict = {'size': 10, 'color': 'w'})
        # 显示最新时间
        ax.text(0.77, 0.01, 'last eob: {0}'.format(last_eob), transform=ax.transAxes, fontdict = {'size': 9, 'color': 'w'})

        # 显示k线信息文本,初始化显示为空
        # 取最新的k
        last_k = df.iloc[-1]
        # 获取开高低收
        Open = last_k.open
        High = last_k.high
        Low = last_k.low
        Close = last_k.close
        Volume = last_k.volume
        Amount = last_k.amount
        eob = last_k.eob

        k_info_text = 'Open:  {0: >25.0f}\nHigh:   {1: >25.0f}\nLow:    {2: >25.0f}\nClose:  {3: >25.0f}\nVolume: {4: >23}\nAmount: {5: >18.0f}\neob: {6}'\
            .format(Open, High, Low, Close, Volume, Amount, eob)
        position_price_ax_text = ax.text(0.01, 0.02, k_info_text, transform=ax.transAxes, fontdict={'size': 8, 'color': 'w'})

        # 显示用户鼠标点击的点
        position_price_pos_ax_text = ax.text(round(k_num/2), df.close.mean(), '', fontdict={'size': 10, 'color': 'y'})

        # 解决横坐标过多的问题, 这里每5个横坐标显示一次
        xtick_num = round(len(ax.get_xticklabels()) / 5)
        continue_time = 0
        for label in ax.get_xticklabels():
            continue_time += 1
            if continue_time % xtick_num == 0:
                # 这些保留下来, 其他的都隐藏掉
                continue
            label.set_visible(False)

        # 保存变量信息
        self.ax_variables_dict[ax]['index'] = index
        self.ax_variables_dict[ax]['symbol'] = symbol
        self.ax_variables_dict[ax]['frequency'] = frequency
        self.ax_variables_dict[ax]['k_num'] =k_num
        self.ax_variables_dict[ax]['df'] = df
        #  self.ax_variables_dict[ax]['candlestick_ohlc_list'] = candlestick_ohlc_list
        self.ax_variables_dict[ax]['k_num_ax_text'] = k_num_ax_text
        self.ax_variables_dict[ax]['frequency_ax_text'] = frequency_ax_text
        self.ax_variables_dict[ax]['position_price_ax_text'] = position_price_ax_text
        self.ax_variables_dict[ax]['position_price_pos_ax_text'] = position_price_pos_ax_text

        # 保存当前的k线坐标, 默认为0
        self.ax_variables_dict[ax]['x_position'] = 0

    def get_ax(self, x, y):
        """ 根据屏幕坐标获取当前的ax """
        if self.ax_num == 1:
            # 1
            return self.ax_list[0]
        else:
            # 4
            if 0 <= y <= 430:
                # ax4
                return self.ax_list[3]
            elif 430 < y <= 890:
                # ax3
                return self.ax_list[2]
            elif 890 < y <= 1340:
                # ax2
                return self.ax_list[1]
            else:
                # ax1
                return self.ax_list[0]

    def band_action(self):
        """ 绑定用户操作回调函数 """
        def show_k_info_motion(event):
            """ 鼠标移动显示k线信息 """
            try:
                if self.show_k_info_motion_is_first_flag:
                    self.show_k_info_motion_is_first_flag = False
                    return

                # 获取当前横坐标向下取整就是数据的索引
                if event.xdata is None:
                    return

                # 获取当前ax
                current_ax = self.get_ax(event.x, event.y)

                # 获取当前ax的信息字典
                ax_variables = self.ax_variables_dict[current_ax]

                # 当前k线坐标
                x_position = math.floor(event.xdata)
                if x_position < 0:
                    # 鼠标移动到了图的最左端左边,超出索引
                    return

                # 取上一次的k线坐标
                last_x_position = ax_variables['x_position']
                if x_position == last_x_position:
                    # 如果现在的k线坐标没有发生改变,就忽略本次运行
                    return
                else:
                    # 更新k线坐标
                    ax_variables['x_position'] = x_position

                # 取出对应的df
                df_data = ax_variables['df']

                try:
                    # 这里的df只是祛除了一行
                    df = df_data.iloc[x_position]
                except IndexError:
                    # 如果用户鼠标移动到了图像的最右边并点击,这个时候索引会超出df的大小,报这个错误,忽略就可以了
                    return

                # 获取开高低收
                Open = df.open
                High = df.high
                Low = df.low
                Close = df.close
                Volume = df.volume
                Amount = df.amount
                eob = df.eob

                # 获取坐标价格text控件
                position_price_ax_text = ax_variables['position_price_ax_text']

                # 设置k线价格信息
                position_price_ax_text.set_text('Open:  {0: >25.0f}\nHigh:   {1: >25.0f}\nLow:    {2: >25.0f}\nClose:  {3: >25.0f}\nVolume: {4: >23}\nAmount: {5: >18.0f}\neob: {6}'\
                    .format(Open, High, Low, Close, Volume, Amount, eob))

                # 更新图像
                self.fig.canvas.draw_idle()

            except Exception as err:
                # 有时候取到的是ax外,取值返回None出错
                traceback.print_exc()
                print(err)

        def show_position_price_motion(event):
            """ 鼠标点击显示当前坐标点的价格 """
            try:
                if self.show_position_price_motion_is_first_flag:
                    self.show_position_price_motion_is_first_flag = False
                    return

                # 获取当前横坐标向下取整就是数据的索引
                if event.xdata is None:
                    return

                # 当前坐标价格
                position_price = event.ydata

                # 获取当前ax
                current_ax = self.get_ax(event.x, event.y)

                # 获取当前ax的信息字典
                ax_variables = self.ax_variables_dict[current_ax]

                # 获取坐标文本点
                position_price_pos_ax_text = ax_variables['position_price_pos_ax_text']

                # 设置坐标点位置,减0.8是修正显示的误差
                position_price_pos_ax_text.set_position((event.xdata - 0.8, event.ydata - 0.8))
                # 设置坐标点图案
                position_price_pos_ax_text.set_text('♦ {0:.3f}'.format(position_price))

                # 更新图像
                self.fig.canvas.draw_idle()

            except Exception as err:
                # 有时候取到的是ax外,取值返回None出错
                traceback.print_exc()
                print(err)

        def motion_debug(event):
            """ DEBUG 用户事件 """
            print("x: {0} y: {1}".format(event.x, event.y))

        # 绑定鼠标点击回调
        #  self.fig.canvas.mpl_connect('button_press_event', motion_debug)
        self.fig.canvas.mpl_connect('button_press_event', show_position_price_motion)
        self.fig.canvas.mpl_connect('motion_notify_event', show_k_info_motion)

    def show_pic(self):
        """ 显示画布 """
        # 显示图像
        plt.show()
