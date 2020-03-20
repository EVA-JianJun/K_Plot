# K_Plot

## 只是一个使用matplotlib画k线的例子

![K_Plot][1]

## 使用了matplotlib，图像风格使用了qbstyles，k线作图使用了过时的mpl包mpl_finance

[matplotlib GitHub][2]
[qbstyles GitHub][3]
[mpl_finance GitHub][4]

## 目前实现的功能有

* **自动更新**：通过传入特定参数的k线数据获取函数，可以自动回调函数并自动作图更新；
* **鼠标左键**：鼠标左键点击，自动定位到对于k线并标注位置，显示选择的k线OHLC、成交量，持仓量等数据；
* **鼠标右键**：右键点击图像会标注当前点击位置的价格；
* **键盘移动**：使用键盘左右键可以移动当前显示的k线信息；

## 使用注意

其实还可以开启十字线，只是由于matplotlib的效率实在太低，占cpu严重，又因为Python最多只能使用单核性能，开启十字线后体验太差，由于我也用不到，就关闭了。

除了效率差外，值得注意的是，matpltlib默认使用后端GUI是TkAgg，Tk是只支持单线程调用的，所以如果要魔改我的代码，需要注意的是如果启动多个线程想来调用mpl，那么很有可能会报一个：

    RuntimeError: main thread is not in main loop

所以这里使用了底层的注册回调函数的api：

    self.win = self.fig.canvas.manager.window
            self._after_func_id_list = list()
            for i in range(5760):
                # 24个小时循环调用
                sleep_time = next_time_sleep + i * auto_frequency
                exec("self._after_func_id_list.append(self.win.after({0} * 1000,     self._tell_draw_idle))".format(sleep_time))

然后很傻的定期定时运行了~~(24个小时)~~七天，不过效果确实达到了，所以如果要后续动态修改什么，请多做做尝试。

对了，K_Plot是可以在ipython中使用的，注意把df的格式换成你的就可以了，目前只是观察调试使用不占资源，如果是对性能有要求的地方最好不要启动任何的gui，一是阻塞的问题，二是稳定性的问题，三是占资源，特别matplotlib动态作图效率真的差。

这只是一个画k线的例子。

  [1]: https://weibo-jianjun.oss-cn-shanghai.aliyuncs.com/article_img/K_Plot.png
  [2]: https://github.com/matplotlib/matplotlib
  [3]: https://github.com/quantumblacklabs/qbstyles
  [4]: https://github.com/matplotlib/mpl_finance
  [5]: https://github.com/quantumblacklabs/qbstyles