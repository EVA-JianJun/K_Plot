#!/use/bin/dev python
# -*- coding: utf-8 -*-
""" 画K好看的线图 """
# 依赖mpl_finance qbstyles
import math
import time
import threading
import traceback
from qbstyles import mpl_style
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.widgets import Cursor
from mpl_finance import candlestick_ohlc
"""
有个不想处理的bug:
如果才开始画的图为300s的,然后重复调用了band_df_func函数,
绑定了60s的数据,那么60s的数据不会刷新,需要等300s后线程调用plot_k函数后
下次开始周期才会变成60s,对于这种问题,如果需要换图像,从大周期向小周期换
先stop掉实例,然后新建实例就可以了,也不是debug不掉,懒得写,反正新建就完事了
速度快的,记得之前把原来的实例给我stop掉,不然会支持报错,也不影响使用,只是看着难受
"""

# 使用qbstyles风格, 也可以换成其他的
mpl_style(dark=True)

# 是否打开debug输出
DEBUG_FLAG = False

class My_Logging():
    def __init__(self, show=True):
        self._show = show

    def print(self, *args, **kwargs):
        if self._show:
            print(*args, **kwargs)

class K_Plot():

    def __init__(self, ax_num=1):
        """ 初始化 """
        # ************ 系统变量 ************
        # 事发第一次触发回调模式不触发逻辑,这是由于用户最大化会触发回调
        self._show_k_info_motion_is_first_flag = True
        self._show_position_price_motion_is_first_flag = True

        # 日志
        #  self._my_logging = My_Logging(DEBUG_FLAG)
        self._my_logging = My_Logging(DEBUG_FLAG)

        # 自动画图结束flag
        self._stop_auot_plot_flag = False

        # 画图锁
        self._plot_lock = threading.Lock()
        # 更新图锁
        self._draw_idle_lock = threading.Lock()

        # ************ 作图变量 ************
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
#
        self.win = self.fig.canvas.manager.window

        """ 注册自动刷新图像功能 """
        # 由于作图最小周期默认为15s,且默认fix为3,我们这里取了15s的最小周期并使用稍大的fix=5
        auto_frequency = 15
        auto_fix = 5
        # 获取当前时间
        now_ts = time.time()
        # 计算下次运行需要等待的时间,由于win.after函数只能接受整数,所以这里要取整
        next_time_sleep = math.floor(auto_frequency - (now_ts % auto_frequency) + auto_fix)
        # next_time_sleep后应该刷新图像,之后每隔auto_frequency后刷新一次
        # 保存定时任务函数id
        self._after_func_id_list = list()
        for i in range(5760 * 7):
            # 7天内循环调用
            sleep_time = next_time_sleep + i * auto_frequency
            exec("self._after_func_id_list.append(self.win.after({0} * 1000, self._tell_draw_idle))".format(sleep_time))

        # 开启动态作图
        plt.ion()
        # 显示图像
        plt.show()

        # 设置窗口标题
        self.fig.canvas.set_window_title('K_Plot')

        # ax 变量字典,用以保存各个ax中的变量信息
        self.ax_variables_dict = dict()
        for ax in self.ax_list:
            self.ax_variables_dict[ax] = dict()

        # 自动作图ax信息字典
        self._auto_plot_ax_dict = dict()
        for ax in self.ax_list:
            self._auto_plot_ax_dict[ax] = dict()

        # 显示鼠标跟随十字线,这里需要创建变量名不同的变量,不然只会显示一个
        self._cursor_list = list()

        # 调整子图间距, 百分比
        plt.subplots_adjust(top=0.97, bottom=0.02, hspace=0.23, left=0.1, right=0.95)

        # 创建ax列表生成器
        def generate_ax_list():
            while True:
                for ax in self.ax_list:
                    yield ax

        self._get_next_ax_gen = generate_ax_list()

        # 绑定回调
        self._band_action()

    def _get_ax(self, x, y):
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

    def _band_action(self):
        """ 绑定用户操作回调函数 """
        def show_k_info_motion(event):
            """ 鼠标点击显示k线信息 """
            try:
                if self._show_k_info_motion_is_first_flag:
                    self._show_k_info_motion_is_first_flag = False
                    return

                if event.button != 1:
                    # 如果按下的不是左键就退出
                    return

                # 获取当前横坐标向下取整就是数据的索引
                if event.xdata is None:
                    return

                # 获取当前ax
                current_ax = self._get_ax(event.x, event.y)

                # 获取当前ax的信息字典
                ax_variables = self.ax_variables_dict[current_ax]

                # 当前k线坐标, 加0.3进行修正
                x_position = math.floor(event.xdata + 0.3)
                if x_position < 0:
                    # 鼠标移动到了图的最左端左边,超出索引
                    return

                # 取上一次的k线坐标
                try:
                    last_x_position = ax_variables['x_position']
                except KeyError:
                    # 如果当前ax未作图,会触发KeyError异常
                    return
                if x_position == last_x_position:
                    # 如果现在的k线坐标没有发生改变,就忽略本次运行
                    return
                else:
                    # 更新k线坐标
                    ax_variables['x_position'] = x_position

                # 取出对应的df
                df_data = ax_variables['df']

                try:
                    # 这里的df只是取了一行
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
                position_price_ax_text.set_text('Open:  {0: >23.3f}\nHigh:   {1: >23.3f}\nLow:    {2: >23.3f}\nClose:  {3: >23.3f}\nVolume: {4: >23}\nAmount: {5: >18.0f}\neob: {6}'\
                    .format(Open, High, Low, Close, Volume, Amount, eob))

                # 当前k线位置标记
                k_position_code_ax_text = ax_variables['k_position_code_ax_text']

                k_position_code_ax_text.set_position((x_position - .5, High))

                self._draw_idle_lock.acquire()
                try:
                    # 更新图像
                    self.fig.canvas.draw_idle()
                finally:
                    self._draw_idle_lock.release()

            except Exception as err:
                # 有时候取到的是ax外,取值返回None出错
                traceback.print_exc()
                print(err)

        def show_position_price_motion(event):
            """ 鼠标点击显示当前坐标点的价格 """
            try:
                if self._show_position_price_motion_is_first_flag:
                    self._show_position_price_motion_is_first_flag = False
                    return

                if event.button != 3:
                    # 如果按下的不是右键就退出
                    return

                # 获取当前横坐标向下取整就是数据的索引
                if event.xdata is None:
                    return

                # 当前坐标价格
                position_price = event.ydata

                # 获取当前ax
                current_ax = self._get_ax(event.x, event.y)

                # 获取当前ax的信息字典
                ax_variables = self.ax_variables_dict[current_ax]

                # 获取坐标文本点
                position_price_pos_ax_text = ax_variables['position_price_pos_ax_text']

                # 设置坐标点位置,减0.8是修正显示的误差
                position_price_pos_ax_text.set_position((event.xdata - 0.8, event.ydata))
                # 设置坐标点图案
                position_price_pos_ax_text.set_text('♦ {0:.3f}'.format(position_price))

                self._draw_idle_lock.acquire()
                try:
                    # 更新图像
                    self.fig.canvas.draw_idle()
                finally:
                    self._draw_idle_lock.release()

            except Exception as err:
                # 有时候取到的是ax外,取值返回None出错
                traceback.print_exc()
                print(err)

        def move_k_info_motion(event):
            """ 键盘左右按键移动显示k线信息 """
            try:
                # 获取当前横坐标向下取整就是数据的索引
                if event.xdata is None:
                    return

                # 获取当前ax
                current_ax = self._get_ax(event.x, event.y)

                # 获取当前ax的信息字典
                ax_variables = self.ax_variables_dict[current_ax]

                # 取上一次的k线坐标
                try:
                    last_x_position = ax_variables['x_position']
                except KeyError:
                    # 如果当前ax未作图,会触发KeyError异常
                    return

                # 根据用户按键移动k线价格坐标
                if event.key == 'left':
                    if last_x_position == 0:
                        # 如果原来的坐标在第一根k线上,那么就不再继续了
                        return
                    new_x_position = last_x_position - 1
                elif event.key == 'right':
                    new_x_position = last_x_position + 1
                else:
                    # 其他情况退出
                    return

                self._my_logging.print(last_x_position, new_x_position)

                # 取出对应的df
                df_data = ax_variables['df']

                try:
                    # 这里的df只是取了一行
                    df = df_data.iloc[new_x_position]
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
                position_price_ax_text.set_text('Open:  {0: >23.3f}\nHigh:   {1: >23.3f}\nLow:    {2: >23.3f}\nClose:  {3: >23.3f}\nVolume: {4: >23}\nAmount: {5: >18.0f}\neob: {6}'\
                    .format(Open, High, Low, Close, Volume, Amount, eob))

                # 当前k线位置标记
                k_position_code_ax_text = ax_variables['k_position_code_ax_text']

                k_position_code_ax_text.set_position((new_x_position - .5, High))

                self._draw_idle_lock.acquire()
                try:
                    # 更新图像
                    self.fig.canvas.draw_idle()
                finally:
                    self._draw_idle_lock.release()

                # 更新k线坐标
                ax_variables['x_position'] = new_x_position

            except Exception as err:
                # 有时候取到的是ax外,取值返回None出错
                traceback.print_exc()
                print(err)

        def motion_debug(event):
            """ DEBUG 用户事件 """
            self.event = event
            print("event.name: ", event.name)
            print("event.key: ", event.key)
            print("event.x: ", event.x)
            print("event.y: ", event.y)
            print("event.xdata: ", event.xdata)
            print("event.ydata: ", event.ydata)

        # DEBUG 回调测试
        # 键盘按键测试
        #  self.fig.canvas.mpl_connect('key_press_event', motion_debug)
        # 鼠标按键测试
        #  self.fig.canvas.mpl_connect('button_press_event', motion_debug)

        """ 绑定鼠标点击回调 """
        # 按下右键标注当前鼠标位置的价格信息
        self.fig.canvas.mpl_connect('button_press_event', show_position_price_motion)
        # 按下鼠标左键显示当前k线的信息
        self.fig.canvas.mpl_connect('button_press_event', show_k_info_motion)

        self.fig.canvas.mpl_connect('key_press_event', move_k_info_motion)

    def _tell_draw_idle(self):
        """ 告诉TkAgg后端作图的函数 """
        # Tkinter是单线程的,如果在多线程中调用就会出错
        # RuntimeError: main thread is not in main loop
        self._draw_idle_lock.acquire()
        try:
            if self._stop_auot_plot_flag:
                return
            # 更新图像
            self.fig.canvas.draw_idle()
        finally:
            self._draw_idle_lock.release()
        self._my_logging.print('draw_idle!')

    def plot_k(self, df, ax='Default'):
        """ 在ax子图上画k线 """
        self._plot_lock.acquire()
        try:
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
            #  self._cursor_list.append(Cursor(ax, useblit=True, color='w', linewidth=1))

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

            # 开高低收等信息
            k_info_text = 'Open:  {0: >23.3f}\nHigh:   {1: >23.3f}\nLow:    {2: >23.3f}\nClose:  {3: >23.3f}\nVolume: {4: >23}\nAmount: {5: >18.0f}\neob: {6}'\
                .format(Open, High, Low, Close, Volume, Amount, eob)
            position_price_ax_text = ax.text(0.01, 0.04, k_info_text, transform=ax.transAxes, fontdict={'size': 9, 'color': 'w'})

            # 当前显示的k线x坐标,默认显示最新一根
            x_position = len(df) - 1

            # 显示当前k线位置标记,默认显示最新一根的上面,减0.5进行位置修正
            k_position_code_ax_text = ax.text(x_position - .5, High, '▼', fontdict={'size': 8, 'color': 'lime'})

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
            self.ax_variables_dict[ax]['k_position_code_ax_text'] = k_position_code_ax_text

            # 保存当前的k线坐标, 默认为0
            self.ax_variables_dict[ax]['x_position'] = x_position

        finally:
            self._plot_lock.release()

    def band_df_func(self, df_func, frequency, fix=3, ax='Default'):
        """
        [summary]
            绑定用户函数

        [description]
            绑定一个获取df的函数,并根据k线周期在+fix后自动运行函数刷新数据并在ax上作图

        Parameters
        ----------
        df_func : {[function]}
            [description]
                获取df的函数,该函数不接受任何参数,并根据当前时间返回最新的k线df
        frequency : {[int]}
            [description]
                该函数获取的k线的周期,单位秒s,类似int
        fix : {number}, optional
            [description] (the default is 5, which [default_description])
                自动刷新数据不会在整点运行,会在整点加fix秒运行
        ax : {str}, optional
            [description] (the default is 'Default', which [default_description])
                该数据显示的ax,不传入ax的话系统默认分配下一个ax,并循环重复覆盖使用
        """

        if ax == 'Default':
            # 如果用户未指定,就使用生成器生成一个
            ax = next(self._get_next_ax_gen)

        if isinstance(ax, int):
            # 如果是数字就说明用户指定了ax的序号
            try:
                ax = self.ax_list[ax]
            except IndexError:
                print("\033[0;36;41max序号指定错误!\033[0m")
                return
            else:
                # 这种情况下一般是用户重新指定了ax,那么就在主进程中画图一次,手动更新图像
                # 画图
                df = df_func()
                self.plot_k(df, ax)
                # 更新图像
                self._draw_idle_lock.acquire()
                try:
                    if self._stop_auot_plot_flag:
                        return
                    # 更新图像
                    self.fig.canvas.draw_idle()
                finally:
                    self._draw_idle_lock.release()
                self._my_logging.print('draw_idle right!')

        try:
            auto_plot_ax_info = self._auto_plot_ax_dict[ax]
        except KeyError:
            print("\033[0;36;41m指定的ax错误!\033[0m")
            return

        # 保存数据
        auto_plot_ax_info['df_func'] = df_func
        auto_plot_ax_info['frequency'] = frequency
        auto_plot_ax_info['fix'] = fix

        def auto_plot(ax):
            # 到时间自动画图,死循环一直画
            while True:
                try:
                    if self._stop_auot_plot_flag:
                        self._my_logging.print("退出!")
                        return
                    # 获取自动画图ax信息
                    auto_plot_ax_info = self._auto_plot_ax_dict[ax]
                    # 获取用户画图函数
                    df_func = auto_plot_ax_info['df_func']
                    # 获取频率
                    frequency = auto_plot_ax_info['frequency']
                    # 获取fix
                    fix = auto_plot_ax_info['fix']

                    # 画图
                    df = df_func()
                    self.plot_k(df, ax)

                    # 获取当前时间
                    now_ts = time.time()
                    # 计算下次运行需要等待的时间
                    next_time_sleep = frequency - (now_ts % frequency) + fix
                    self._my_logging.print("{0}s后更新.".format(next_time_sleep))
                    # 等待
                    time.sleep(next_time_sleep)
                except Exception as err:
                    print("\033[0;36;41m自动更新作图错误!\033[0m")
                    traceback.print_exc()
                    print(err)
                    # 出错就退出,不然会一直出错
                    return
        try:
            # 先试着取下看看是不是已经有自动画图线程了
            auto_plot_ax_info['auto_plot_th']
        except KeyError:
            # 表示没创建过,那么创建新的
            # 启动自动画图线程
            auto_plot_th = threading.Thread(target=auto_plot, args=(ax,))
            auto_plot_th.start()
            # 然后保存这个变量
            auto_plot_ax_info['auto_plot_th'] = auto_plot_th

    def stop(self, close_windows=True):
        """ 停止自动作图并退出 """
        # 这个会把自动plot线程给取消
        self._stop_auot_plot_flag = True
        # 这个把自动刷新图像任务id给取消,不取消结束画图或持续报错
        for after_func_id in self._after_func_id_list:
            self.win.after_cancel(after_func_id)

        if close_windows:
            # 关闭窗口
            plt.close()

class K_Plot_Simple():
    """ 简单画图 """
    def __init__(self):
        """ 初始化 """
        # 创建画布
        self.fig, self.ax = plt.subplots(figsize=(18, 12), ncols=1, nrows=1)

        self.ax_variables_dict = dict()
        self.ax_variables_dict[self.ax] = dict()

        # 更新图锁
        self._draw_idle_lock = threading.Lock()

        # 开启动态作图
        plt.ion()
        # 显示图像
        plt.show()

        # 设置窗口标题
        self.fig.canvas.set_window_title('K_Plot_Simple')

        # 调整子图间距, 百分比
        plt.subplots_adjust(top=0.95, bottom=0.05, hspace=0.23, left=0.05, right=0.95)

        # 绑定回调
        self._band_action()

    def _band_action(self):
        """ 绑定用户操作回调函数 """
        def show_k_info_motion(event):
            """ 鼠标点击显示k线信息 """
            try:
                if event.button != 1:
                    # 如果按下的不是左键就退出
                    return

                # 获取当前横坐标向下取整就是数据的索引
                if event.xdata is None:
                    return

                # 获取当前ax
                current_ax = self.ax

                # 获取当前ax的信息字典
                ax_variables = self.ax_variables_dict[current_ax]

                # 当前k线坐标, 加0.3进行修正
                x_position = math.floor(event.xdata + 0.3)
                if x_position < 0:
                    # 鼠标移动到了图的最左端左边,超出索引
                    return

                # 取上一次的k线坐标
                try:
                    last_x_position = ax_variables['x_position']
                except KeyError:
                    # 如果当前ax未作图,会触发KeyError异常
                    return
                if x_position == last_x_position:
                    # 如果现在的k线坐标没有发生改变,就忽略本次运行
                    return
                else:
                    # 更新k线坐标
                    ax_variables['x_position'] = x_position

                # 取出对应的df
                df_data = ax_variables['df']

                try:
                    # 这里的df只是取了一行
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
                position_price_ax_text.set_text('Open:  {0: >23.3f}\nHigh:   {1: >23.3f}\nLow:    {2: >23.3f}\nClose:  {3: >23.3f}\nVolume: {4: >23}\nAmount: {5: >18.0f}\neob: {6}'\
                    .format(Open, High, Low, Close, Volume, Amount, eob))

                # 当前k线位置标记
                k_position_code_ax_text = ax_variables['k_position_code_ax_text']

                k_position_code_ax_text.set_position((x_position - .5, High))

                self._draw_idle_lock.acquire()
                try:
                    # 更新图像
                    self.fig.canvas.draw_idle()
                finally:
                    self._draw_idle_lock.release()

            except Exception as err:
                # 有时候取到的是ax外,取值返回None出错
                traceback.print_exc()
                print(err)

        def show_position_price_motion(event):
            """ 鼠标点击显示当前坐标点的价格 """
            try:
                if event.button != 3:
                    # 如果按下的不是右键就退出
                    return

                # 获取当前横坐标向下取整就是数据的索引
                if event.xdata is None:
                    return

                # 当前坐标价格
                position_price = event.ydata

                # 获取当前ax
                current_ax = self.ax

                # 获取当前ax的信息字典
                ax_variables = self.ax_variables_dict[current_ax]

                # 获取坐标文本点
                position_price_pos_ax_text = ax_variables['position_price_pos_ax_text']

                # 设置坐标点位置,减0.8是修正显示的误差
                position_price_pos_ax_text.set_position((event.xdata - 0.8, event.ydata))
                # 设置坐标点图案
                position_price_pos_ax_text.set_text('♦ {0:.3f}'.format(position_price))

                self._draw_idle_lock.acquire()
                try:
                    # 更新图像
                    self.fig.canvas.draw_idle()
                finally:
                    self._draw_idle_lock.release()

            except Exception as err:
                # 有时候取到的是ax外,取值返回None出错
                traceback.print_exc()
                print(err)

        def move_k_info_motion(event):
            """ 键盘左右按键移动显示k线信息 """
            try:
                # 获取当前横坐标向下取整就是数据的索引
                if event.xdata is None:
                    return

                # 获取当前ax
                current_ax = self.ax

                # 获取当前ax的信息字典
                ax_variables = self.ax_variables_dict[current_ax]

                # 取上一次的k线坐标
                try:
                    last_x_position = ax_variables['x_position']
                except KeyError:
                    # 如果当前ax未作图,会触发KeyError异常
                    return

                # 根据用户按键移动k线价格坐标
                if event.key == 'left':
                    if last_x_position == 0:
                        # 如果原来的坐标在第一根k线上,那么就不再继续了
                        return
                    new_x_position = last_x_position - 1
                elif event.key == 'right':
                    new_x_position = last_x_position + 1
                else:
                    # 其他情况退出
                    return

                # 取出对应的df
                df_data = ax_variables['df']

                try:
                    # 这里的df只是取了一行
                    df = df_data.iloc[new_x_position]
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
                position_price_ax_text.set_text('Open:  {0: >23.3f}\nHigh:   {1: >23.3f}\nLow:    {2: >23.3f}\nClose:  {3: >23.3f}\nVolume: {4: >23}\nAmount: {5: >18.0f}\neob: {6}'\
                    .format(Open, High, Low, Close, Volume, Amount, eob))

                # 当前k线位置标记
                k_position_code_ax_text = ax_variables['k_position_code_ax_text']

                k_position_code_ax_text.set_position((new_x_position - .5, High))

                self._draw_idle_lock.acquire()
                try:
                    # 更新图像
                    self.fig.canvas.draw_idle()
                finally:
                    self._draw_idle_lock.release()

                # 更新k线坐标
                ax_variables['x_position'] = new_x_position

            except Exception as err:
                # 有时候取到的是ax外,取值返回None出错
                traceback.print_exc()
                print(err)

        def motion_debug(event):
            """ DEBUG 用户事件 """
            self.event = event
            print("event.name: ", event.name)
            print("event.key: ", event.key)
            print("event.x: ", event.x)
            print("event.y: ", event.y)
            print("event.xdata: ", event.xdata)
            print("event.ydata: ", event.ydata)

        # DEBUG 回调测试
        # 键盘按键测试
        #  self.fig.canvas.mpl_connect('key_press_event', motion_debug)
        # 鼠标按键测试
        #  self.fig.canvas.mpl_connect('button_press_event', motion_debug)

        """ 绑定鼠标点击回调 """
        # 按下右键标注当前鼠标位置的价格信息
        self.fig.canvas.mpl_connect('button_press_event', show_position_price_motion)
        # 按下鼠标左键显示当前k线的信息
        self.fig.canvas.mpl_connect('button_press_event', show_k_info_motion)

        self.fig.canvas.mpl_connect('key_press_event', move_k_info_motion)

    def plot_k(self, df):
        """ 在ax子图上画k线 """
        ax = self.ax
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
        #  self._cursor_list.append(Cursor(ax, useblit=True, color='w', linewidth=1))

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

        # 开高低收等信息
        k_info_text = 'Open:  {0: >23.3f}\nHigh:   {1: >23.3f}\nLow:    {2: >23.3f}\nClose:  {3: >23.3f}\nVolume: {4: >23}\nAmount: {5: >18.0f}\neob: {6}'\
            .format(Open, High, Low, Close, Volume, Amount, eob)
        position_price_ax_text = ax.text(0.01, 0.04, k_info_text, transform=ax.transAxes, fontdict={'size': 9, 'color': 'w'})

        # 当前显示的k线x坐标,默认显示最新一根
        x_position = len(df) - 1

        # 显示当前k线位置标记,默认显示最新一根的上面,减0.5进行位置修正
        k_position_code_ax_text = ax.text(x_position - .5, High, '▼', fontdict={'size': 8, 'color': 'lime'})

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
        self.ax_variables_dict[ax]['k_position_code_ax_text'] = k_position_code_ax_text

        # 保存当前的k线坐标, 默认为0
        self.ax_variables_dict[ax]['x_position'] = x_position
