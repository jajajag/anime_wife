# 抽二次元老婆

一个适用于HoshinoBot的随机二次元老婆插件

## 加入了一些私人订制的功能 by Jag
* 用一个db来储存历史数据
* 重置牛老婆改为次数+1
* 给被牛的人补偿1条命
* 增加老婆档案查询老婆历史信息
* 增加复活吧我的爱人，复活上一个抽到/换到的老婆
* 增加跟你爆了，用2条命必定反牛成功且不补偿对方次数
* 增加查新，检查别人的老婆是否没出过
* 增加抽/牛/换老婆时显示是否出新

## 如何安装

1. 在HoshinoBot的插件目录modules下clone本项目

    `git clone https://github.com/Rinco304/AnimeWife`

2. 下载 `Releases` 中的  [wife.rar](https://github.com/Rinco304/AnimeWife/releases/download/v1.0/wife.rar) 并将其解压到 `/res/img` 目录下

3. 在 `config/__bot__.py`的模块列表里加入 `AnimeWife`

4. 重启HoshinoBot

2024-6-16：更新了一批新的老婆在 `Releases` 与网盘分享中，下载后将图片解压到 `/res/img/wife` 文件夹中即可 [wife2.rar](https://github.com/Rinco304/AnimeWife/releases/download/v1.0/wife2.rar)
## 怎么使用

```
[抽老婆] 看看今天的二次元老婆是谁
[交换老婆] @某人 + 交换老婆
[牛老婆] 2/3概率牛到别人老婆(1次/日)
[查老婆] 加@某人可以查别人老婆
[查新] @某人查别人的老婆是否没出过
[重置牛老婆] 加@某人可以重置别人牛的次数
[跟你爆了] 消耗2条命抢回自己被牛走的老婆，且不补偿对方次数
[复活吧我的爱人] 复活上一次被牛走的老婆
[老婆档案] 加@某人可以查看别人的老婆档案
[切换ntr开关状态]
```

## 备注

`config` 文件夹是用于记录群友每日抽的老婆信息，不用于配置插件，插件的配置位于 ` animewife.py ` 文件中

```
# 群管理员每天可添加老婆的次数
_max=1

# 当超出次数时的提示
max_notice = f'为防止滥用，管理员一天最多可添加{_max}次，若需添加更多请使用 来杯咖啡 联系维护组'
```

若 `Releases` 中下载速度太慢或下载失败，可以尝试使用百度网盘下载

[网盘下载](https://pan.baidu.com/s/1FbRtczF1h1jIov_CXU1qew?pwd=amls)
提取码：amls

## 参考致谢

| [dailywife](https://github.com/SonderXiaoming/dailywife) | [@SonderXiaoming](https://github.com/SonderXiaoming) |

| [whattoeat](https://github.com/A-kirami/whattoeat) | [@A-kirami](https://github.com/A-kirami) |

| [zbpwife](https://github.com/FloatTech/zbpwife) |（绝大部分老婆图片都是出自这里，个人也添加了一些）
