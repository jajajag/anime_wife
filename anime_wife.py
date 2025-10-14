import asyncio
import base64
import hoshino, random, os, re, filetype, datetime, json
import sqlite3
from hoshino import Service, R, priv, aiorequests
from hoshino.config import RES_DIR
from hoshino.typing import CQEvent
from hoshino.util import DailyNumberLimiter
from html import unescape
from .noise import add_invisible_noise_content
from io import BytesIO
from PIL import Image


sv_help = '''
[抽老婆] 看看今天的二次元老婆是谁
[换老婆] @某人 + 交换老婆(5次/日)
[牛老婆] 2/3概率牛到别人老婆(1次/日)
[查老婆] 加@某人可以查别人老婆(5次/日)
[日老婆] 消耗2条命可以提高和别人老婆的好感度
[添加老婆+人物名称+图片] 添加老婆到待审查图库(1次/日)
[离婚] 和二次元老婆离婚(1次/日)
[跟你爆了] 消耗2条命抢回自己被牛走的老婆，且不补偿对方次数
[复活吧我的爱人] 复活上一次被牛走的老婆
[老婆档案] 加@某人可以查看别人的老婆档案
[老婆档案] 加@某人可以查看别人的老婆图鉴
[重置牛老婆] 加@某人可以重置别人牛的次数
[切换ntr开关状态]
'''.strip()


sv = Service(
    name = '抽老婆',  #功能名
    use_priv = priv.NORMAL, #使用权限   
    manage_priv = priv.ADMIN, #管理权限
    visible = True, #可见性
    enable_on_default = True, #默认启用
    bundle = '娱乐', #分组归类
    help_ = sv_help #帮助说明
)


# 图片路径
imgpath = os.path.join(os.path.expanduser(RES_DIR), 'img', 'wife')
# 待审查的图片文件夹
imgpath_review = os.path.join(os.path.expanduser(RES_DIR), 'img', 'wife_review')

# 牛老婆的成功率
ntr_possibility = 2.0 / 3
# 每日次数限制
daily_limits = {
    'add': 1, # 添加老婆
    'ntr': 1, # 牛老婆
    'ex': 5,  # 交换老婆
    'sc': 5,  # 查老婆
    'div': 1,  # 离婚
    'mate': 2 # 日老婆
}
limiters = {key: DailyNumberLimiter(v) for key, v in daily_limits.items()}


# 加载json数据
def load_group_config(group_id: str) -> int:
    filename = os.path.join(os.path.dirname(__file__), 
                            'config', f'{group_id}.json')
    try:
        with open(filename, encoding='utf8') as f:
            config = json.load(f)
            return config
    except:
        return None


# 写入json数据
def write_group_config(group_id: str, link_id:str, wife_name:str, date:str, 
                       config) -> int:
    config_file = os.path.join(os.path.dirname(__file__), 
                               'config', f'{group_id}.json')
    if config is None:
        config = {}
    if wife_name is not None and date is not None:
        config[link_id] = [wife_name, date]
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False)


def open_db_history():
    # wife_type: gacha, exchange, ntr
    db_name = os.path.join(os.path.dirname(__file__), 'config', f'history.db')
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    create_table_sql = f'''
        CREATE TABLE IF NOT EXISTS wife_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wife_type TEXT,
            user_id INTEGER,
            target_id INTEGER,
            group_id INTEGER,
            wife_name TEXT,
            date TEXT
        )
    '''
    # Create table if not exists
    cursor.execute(create_table_sql)
    return cursor, conn


# Write history to db
def write_db_history(wife_type, user_id, target_id, group_id, wife_name, date):
    # Open db
    cursor, conn = open_db_history()
    insert_sql = '''
        INSERT INTO wife_history
            (wife_type, user_id, target_id, group_id, wife_name, date)
        VALUES (?, ?, ?, ?, ?, ?)
        '''
    # Write to db
    cursor.execute(insert_sql, (wife_type, user_id, target_id, 
                                group_id, wife_name, date))
    conn.commit()
    conn.close()


# JAG: Check if the wife is new
def check_new(group_id, user_id, wife_name):
    cursor, conn = open_db_history()
    wife_name = wife_name.split('.')[0]
    # Check if the wife exists in history
    cursor.execute("""
        SELECT EXISTS(
            SELECT 1 FROM wife_history
            WHERE group_id = ? AND user_id = ? AND wife_name = ?)
    """, (group_id, user_id, wife_name))
    result = cursor.fetchone()[0]
    conn.close()
    # Return a str if the wife is new
    return f'\n是新老婆哦！' if not result else ''


# JAG: Check the #mate
def check_mate(group_id, user_id, wife_name):
    cursor, conn = open_db_history()
    wife_name = wife_name.split('.')[0]
    # Check if the #mate in the history
    cursor.execute("""
        SELECT COUNT(*) FROM wife_history
        WHERE group_id = ? AND user_id = ? 
        AND wife_name = ? AND wife_type = 'mate'
    """, (group_id, user_id, wife_name))
    result = cursor.fetchone()
    mate = result[0] if result else 0
    conn.close()
    # Return the #mate
    return f'\n好感度：{mate}'


@sv.on_fullmatch('抽老婆')
async def animewife(bot, ev: CQEvent):
    # 获取QQ群、群用户QQ信息
    group_id = ev.group_id
    user_id = ev.user_id
    wife_name = None
    # 获取今天的日期，转换为字符串格式
    today = str(datetime.date.today())
    # 载入群组信息
    config = load_group_config(group_id)
    if config != None:
        # 检查用户QQ号是否在配置中
        if str(user_id) in list(config):
            # 检查用户的老婆信息是否是今天
            if config[str(user_id)][1] == today:
                # 是今天，直接返回（一天只能有一个老婆）
                wife_name = config[str(user_id)][0]
            else:
                # 如果不是今天的信息，删除该用户信息重新获取老婆信息
                config.pop(str(user_id), None)
    
    # JAG: Initialize result_new
    result_new = ''
    # 如果没有老婆信息，则进行随机选择
    if wife_name is None:
        if config != None:
            # 删除不是今天的所有老婆信息
            for record_id in list(config):
                if config[record_id][1] != today:
                    config.pop(record_id, None)
        # 随机选择一张老婆的图片，用于获取图片名
        wife_name = random.choice(os.listdir(imgpath))
        # JAG: Check if the wife is new
        result_new = check_new(group_id, user_id, wife_name)
        # JAG: Gacha wife history
        write_db_history('gacha', user_id, 0, group_id, 
                         wife_name.split('.')[0], today)
    # 分割文件名和扩展名，只取图片名返回给用户
    name = wife_name.split('.')
    # 生成返回结果
    result = f'你今天的二次元老婆是{name[0]}哒~\n'
    try:
        # 尝试读取老婆图片，并添加到结果中
        wifeimg = R.img(f'wife/{wife_name}').cqcode
        result += str(wifeimg) + result_new
    except Exception as e:
        hoshino.logger.error(f'读取老婆图片时发生错误{type(e)}')
    # 将选择的老婆信息写入群组配置
    write_group_config(group_id,user_id,wife_name,today,config)
    # 发送消息
    await bot.send(ev,result,at_sender=True)
    

#下载图片
async def download_async(url: str, name: str):
    url = unescape(url)
    resp= await aiorequests.get(url, stream=True)
    if resp.status_code == 404:
        raise ValueError('文件不存在')
    content = await resp.content
    try:
        extension = filetype.guess_mime(content).split('/')[1]
        # 添加不可见噪声
        content = add_invisible_noise_content(content)
        # 经过上述转化固定是jpg格式
        extension = 'jpg'
    except:
        raise ValueError('不是有效文件类型')
    abs_path = os.path.join(imgpath_review, f'{name}.{extension}')
    i = 0
    # 如果文件名重复则重命名
    while os.path.exists(abs_path):
        i += 1
        abs_path = os.path.join(imgpath_review, f"{name}_{i}.{extension}")
    with open(abs_path, 'wb') as f:
        f.write(content)


@sv.on_rex(r'^(添?加老婆)|(添?加老婆)$')
async def add_wife(bot,ev:CQEvent):
    # 获取QQ信息
    user_id = ev.user_id
    # 此注释的代码是仅限bot超级管理员使用，
    # 有需可启用并将下面判断权限的代码注释掉
    #if user_id not in hoshino.config.SUPERUSERS:
    #    return

    # 判断权限，只有用户为群管理员或为bot设置的超级管理员才能使用
    # u_priv = priv.get_user_priv(ev)
    # if u_priv < sv.manage_priv:
        # return
    # 检查用户今天是否已添加过老婆信息
    if not limiters['add'].check(user_id):
        await bot.finish(
            ev, f'为防止滥用，管理员一天最多可添加{daily_limits["add"]}次。', 
            at_sender=True)
    # 提取老婆的名字
    name = ev.message.extract_plain_text().strip()
    # 获得图片信息
    ret = re.search(r"\[CQ:image,file=(.*)?,url=(.*)\]", str(ev.message))
    if not ret:
        # 未获得图片信息
        await bot.finish(ev,'请附带二次元老婆图片~')
    # 获取下载url
    url = ret[2]
    # 下载图片保存到本地
    await download_async(url, name)
    # 如果不是超级管理员，增加用户的添加老婆次数（管理员可一天增加多次）
    if user_id not in hoshino.config.SUPERUSERS:
        limiters['add'].increase(user_id)
    await bot.send(ev,'信息已增加~')


############################## 下面是交换老婆功能 ##############################
class ExchangeManager:
    def __init__(self):
        self.exchange_requests = {}
        self.exchange_in_progress = {}  # 为每个群组添加交换进行标志
        self.exchange_tasks = {}
        
    def insert_exchange_request(self, group_id, user_id, target_id):
        group_id_str = str(group_id)
        user_pair = f"{user_id}-{target_id}"
        group_exchanges = self.exchange_requests.setdefault(group_id_str, {})
        if user_pair not in group_exchanges:
            group_exchanges[user_pair] = "pending"
            self.exchange_in_progress[group_id_str] = True  
            # 标记该群组有交换正在进行

    def remove_exchange_request(self, group_id, user_id, target_id):
        group_id_str = str(group_id)
        user_pair = f"{user_id}-{target_id}"
        group_exchanges = self.exchange_requests.get(group_id_str, {})
        if user_pair in group_exchanges:
            group_exchanges.pop(user_pair)
            if not group_exchanges:  # 如果该群组内没有其他交换请求
                self.exchange_requests.pop(group_id_str, None)
                self.exchange_in_progress[group_id_str] = False  
                # 更新该群组的交换进行标志
    
    def is_exchange_in_progress(self, group_id):
        return self.exchange_in_progress.get(str(group_id), False)
        
    def is_eligible_for_exchange(self, group_id, user_id, target_id):
        group_exchanges = self.exchange_requests.get(str(group_id), {})
        if any(str(user_id) in key or str(target_id) in key \
                for key in group_exchanges):
            # 用户已经存在于当前任何一方的交换请求中
            return False
        return True
        
    def is_exchange_pending(self, group_id, user_id, target_id):
        group_exchanges = self.exchange_requests.get(str(group_id), {})
        user_pair = f"{user_id}-{target_id}"
        return user_pair in group_exchanges \
                and group_exchanges[user_pair] == "pending"
        
    async def handle_timeout(
            self, bot, ev, group_id, user_id, target_id, delay = 60):
        try:
            await asyncio.sleep(delay)  # 默认等待60秒
            # 检查请求是否仍然是pending状态，如果是，则移除
            if self.is_exchange_pending(group_id, user_id, target_id):
                self.remove_exchange_request(group_id, user_id, target_id)
                # 发送交换超时的通知
                await bot.send_group_msg(group_id=group_id, message=f"[CQ:at,qq={user_id}] 你的交换请求已超时，对方无视了你")
        except asyncio.CancelledError:
            pass # 如果任务取消，什么也不做或者进行其他清理工作 
    def get_exchange_by_target(self, group_id, target_id):
        group_id_str = str(group_id)
        target_id_str = str(target_id)
        group_exchanges = self.exchange_requests.get(group_id_str, {})
        for key, status in group_exchanges.items():
            if key.endswith(f"-{target_id_str}") and status == "pending":
                return key.split('-')[0], key.split('-')[1]  
            # 返回发起者和目标者的ID
        return None, None
    # 新增加两个方法来处理定时器任务的存储和取消
    def set_exchange_task(self, group_id, user_id, target_id, task):
        group_id_str = str(group_id)
        user_pair = f"{user_id}-{target_id}"
        self.exchange_tasks[group_id_str] = self.exchange_tasks.get(
                group_id_str, {})
        self.exchange_tasks[group_id_str][user_pair] = task
    
    def cancel_exchange_task(self, group_id, user_id, target_id):
        group_id_str = str(group_id)
        user_pair = f"{user_id}-{target_id}"
        task = self.exchange_tasks.get(group_id_str, {}).pop(user_pair, None)
        if task:
            task.cancel()
            
# Initialize exchange manager
exchange_manager = ExchangeManager()


@sv.on_rex(r'^(交?换老婆)|(交?换老婆)$')
async def exchange_wife(bot, ev: CQEvent):
    # 获取QQ群、群用户QQ信息
    group_id = ev.group_id
    user_id = ev.user_id
    target_id = None
    today = str(datetime.date.today())
    # 获取用户和目标用户的配置信息
    config = load_group_config(group_id)
    # 提取目标用户的QQ号
    for seg in ev.message:
        if seg.type == 'at' and seg.data['qq'] != 'all':
            target_id = int(seg.data['qq'])
            #print("提取目标用户的QQ号：" + str(target_id))
            break
    if not target_id:
        #print("未找到目标用户QQ或者未@对方")
        await bot.finish(ev, '请指定一个要交换老婆的目标', at_sender=True)
    # 检查发起者或目标者是否已经在任何交换中
    if not exchange_manager.is_eligible_for_exchange(
            group_id, user_id, target_id):
        await bot.finish(ev, '双方有人正在进行换妻play中，请稍后再试', 
                       at_sender=True)
    # 如果该群组有交换请求
    if exchange_manager.is_exchange_in_progress(ev.group_id):
        await bot.finish(ev, '正在办理其他人的换妻手续，请稍后再试', 
                       at_sender=True)
    # 检查是否尝试交换给自己
    if user_id == target_id:
        await bot.finish(ev, '不能牛自己', at_sender=True)
    if not config:
        await bot.finish(ev, '没有找到本群婚姻登记信息', at_sender=True)
    # 检查用户和目标用户是否有老婆信息
    if str(user_id) not in config or str(target_id) not in config:
        await bot.finish(ev, '需要双方都有老婆才能交换', at_sender=True)
    # 检查用户的老婆信息是否是今天
    if config[str(user_id)][1] != today:
        await bot.finish(ev, '你的老婆已过期，请抽取新的老婆后再交换', 
                       at_sender=True)
    # 检查目标的老婆信息是否是今天
    if config[str(target_id)][1] != today:
        await bot.finish(ev, '对方的老婆已过期，你也不想要过期的老婆吧', 
                         at_sender=True)
    # JAG: Check exchange limit
    if not limiters['ex'].check(f"{user_id}_{group_id}"):
        await bot.finish(ev, f'已达到每日交换上限（{daily_limits["ex"]}次）', 
                         at_sender=True)
    # JAG: Increase exchange limit by 1
    limiters['ex'].increase(f"{user_id}_{group_id}")

    # 满足交换条件，添加进交换请求列表中
    exchange_manager.insert_exchange_request(group_id, user_id, target_id)
    # 发送交换请求（此处可能会发不出去导致交换请求无法解锁）
    try:
        await bot.send(ev, f'[CQ:at,qq={target_id}] 用户 [CQ:at,qq={user_id}] 想要和你交换老婆，是否同意？\n如果同意(拒绝)请在60秒内发送“同意(拒绝)”', 
                       at_sender=False)
    except Exception as e:
        hoshino.logger.error(f'交换老婆时发生错误{type(e)}')
    # 启动定时器，60秒后如果没有收到回应则自动清除交换请求
    exchange_task = asyncio.create_task(exchange_manager.handle_timeout(
        bot, ev, group_id, user_id, target_id))
    exchange_manager.set_exchange_task(
            group_id, user_id, target_id, exchange_task)


async def handle_ex_wife(user_id, target_id, group_id, agree = False):
    if agree:
        config = load_group_config(group_id)
        # 检索用户和目标用户的老婆信息
        user_wife = config.get(str(user_id), [None])[0]
        target_wife = config.get(str(target_id), [None])[0]
        #print("发起用户老婆名称：" + str(user_wife) + "目标对象老婆名称：" + str(target_wife))
        # 交换图片名
        config[str(user_id)][0], config[str(target_id)][0] = target_wife, \
                user_wife
        
        today = str(datetime.date.today())
        # 更新群组配置文件
        write_group_config(
                str(group_id), str(user_id), target_wife, today, config)
        write_group_config(
                str(group_id), str(target_id), user_wife, today, config)
        # JAG: Exchange wife history
        write_db_history('exchange', user_id, target_id, group_id, 
                         target_wife.split('.')[0], today)
        write_db_history('exchange', target_id, user_id, group_id, 
                         user_wife.split('.')[0], today)
    # 删除exchange_manager中对应的请求用户对记录
    exchange_manager.remove_exchange_request(group_id, user_id, target_id)
    # 取消超时任务
    exchange_manager.cancel_exchange_task(group_id, user_id, target_id)

    
@sv.on_message('group')
async def ex_wife_reply(bot, ev: CQEvent):
    # 如果该群组内没有交换请求
    if not exchange_manager.is_exchange_in_progress(ev.group_id):
        return
    # 存在交换请求
    group_id = ev.group_id
    target_id = ev.user_id
    #print("被请求者:" + str(target_id))
    # 比对该用户是否是用户对中的被请求者
    # 通过被请求者获取发起者id
    initiator_id = exchange_manager.get_exchange_by_target(
            group_id, target_id)[0]
    # 不为空则说明有记录
    if initiator_id:
        # 提取消息文本
        keyword = "".join(seg.data['text'].strip() for seg in ev.message \
                if seg.type == 'text')

        # 寻找关键词的索引位置
        agree_index = keyword.find('同意')
        disagree_index = keyword.find('不同意')
        refuse_index = keyword.find('拒绝')

        # 对“不同意”和“拒绝”做处理，找出两者中首次出现的位置
        disagree_first_index = -1
        if disagree_index != -1 and refuse_index != -1:
            disagree_first_index = min(disagree_index, refuse_index)
        elif disagree_index != -1:
            disagree_first_index = disagree_index
        elif refuse_index != -1:
            disagree_first_index = refuse_index
        
        # 进行判断
        # 如果找到“不同意”或“拒绝”，且它们在“同意”之前出现，或者没找到“同意”
        if disagree_first_index != -1 and (agree_index > disagree_first_index \
                or agree_index == -1):
            message = f'[CQ:at,qq={initiator_id}] 对方拒绝了你的交换请求'
            await handle_ex_wife(initiator_id, target_id, group_id)
            await bot.send(ev, message)
        # 如果仅找到“同意”，或者“同意”在“不同意”或“拒绝”之前出现
        elif agree_index != -1 and (disagree_first_index > agree_index \
                or disagree_first_index == -1):
            # JAG: Check if the wife is new before exchange
            config = load_group_config(group_id)
            target_wife = config.get(str(target_id), [None])[0]
            message = f'[CQ:at,qq={initiator_id}] 交换成功'
            message += check_new(group_id, initiator_id, target_wife)
            await handle_ex_wife(initiator_id, target_id, group_id, True)
            await bot.send(ev, message)


# 重置牛老婆次数限制
#@sv.on_rex(r'^(重置牛老婆)|(重置牛老婆)$')
@sv.on_rex(r'^(重置(牛老婆|日老婆|离婚))$|(重置(牛老婆|日老婆|离婚))$')
async def reset_ntr_wife(bot, ev: CQEvent):
    # 获取QQ信息
    user_id = ev.user_id
    group_id = ev.group_id
    # JAG: Get keyword from regex match
    match = ev['match']
    keyword = match.group(2)
    # 此注释的代码是仅限bot超级管理员使用，
    # 有需可启用并将下面判断权限的代码注释掉
    if user_id not in hoshino.config.SUPERUSERS:
        await bot.finish(ev,"该功能仅限bot管理员使用")
    # 判断权限，只有用户为群管理员或为bot设置的超级管理员才能使用
    # u_priv = priv.get_user_priv(ev)
    # if u_priv < sv.manage_priv:
        # await bot.send(ev,"该功能仅限群管理员或为bot设置的超级管理员使用")
        # return
    target_id = None
    # 提取目标用户的QQ号
    for seg in ev.message:
        if seg.type == 'at' and seg.data['qq'] != 'all':
            target_id = int(seg.data['qq'])
            break
    #if target_id is None:
    #    await bot.finish(ev,"请@要重置的用户")
    target_id = target_id if target_id else user_id
    #limiters['ntr'].reset(f"{target_id}_{group_id}")
    # JAG: Change reset to increment by 1
    if keyword == '牛老婆':
        limiters['ntr'].increase(f"{target_id}_{group_id}", -1)
    elif keyword == '日老婆':
        limiters['mate'].increase(f"{target_id}_{group_id}", -1)
    elif keyword == '离婚':
        limiters['div'].increase(f"{target_id}_{group_id}", -1)
    await bot.send(ev, "已重置次数")
    

# JAG: Helper for ntr_wife and ntr_back_wife
async def ntr_wife_helper(bot, ev: CQEvent, ntr_back=False):
    # 获取QQ群、群用户QQ信息
    load_ntr_statuses()
    group_id = str(ev.group_id)
    if not ntr_statuses.get(group_id, True):
        await bot.finish(ev, '牛老婆功能未开启！', at_sender=False)
    user_id = ev.user_id
    # JAG: Check ntr limit
    if not ntr_back and not limiters['ntr'].check(f"{user_id}_{group_id}"):
        await bot.finish(ev,
            f'为防止牛头人泛滥，一天最多可牛{daily_limits["ntr"]}次（无保底）',
            at_sender=True)
    # JAG: Check ntr_back limit
    if ntr_back and daily_limits['ntr'] \
            - limiters['ntr'].get_num(f"{user_id}_{group_id}") < 2:
        await bot.finish(ev, '你需要2条命来和对方爆了', at_sender=True)
    target_id = None
    today = str(datetime.date.today())
    # 获取用户和目标用户的配置信息
    config = load_group_config(group_id)
    # 提取目标用户的QQ号
    for seg in ev.message:
        if seg.type == 'at' and seg.data['qq'] != 'all':
            target_id = int(seg.data['qq'])
            #print("提取目标用户的QQ号：" + str(target_id))
            break
    if not target_id:
        #print("未找到目标用户QQ或者未@对方")
        await bot.finish(ev, '请指定一个要下手的目标', at_sender=True)
    # 检查发起者或目标者是否已经在任何交换中
    if not exchange_manager.is_eligible_for_exchange(
            group_id, user_id, target_id):
        await bot.finish(ev, '双方有人正在进行换妻play中，请稍后再试', 
                       at_sender=True)
    # 如果该群组有交换请求
    if exchange_manager.is_exchange_in_progress(ev.group_id):
        await bot.finish(ev, '正在办理其他人的换妻手续，很忙，请稍后再试', 
                       at_sender=True)
    # 检查是否尝试交换给自己
    if user_id == target_id:
        await bot.finish(ev, '不能对自己下手', at_sender=True)
    if not config:
        await bot.finish(ev, '没有找到本群婚姻登记信息', at_sender=True)
    # 检查目标用户是否有老婆信息
    if str(target_id) not in config:
        await bot.finish(ev, '对方没有老婆哦', at_sender=True)
    # 检查目标的老婆信息是否是今天
    if config[str(target_id)][1] != today:
        await bot.finish(ev, '对方的老婆已过期，你也不想要过期的老婆吧', 
                       at_sender=True)
    # Get target wife
    target_wife = config.get(str(target_id), [None])[0]
    # Check specific ntr_back condition
    if ntr_back:
        # Get target wife's name
        target_wife_name = target_wife.split('.')[0]
        # Check the db if the wife is ntred from the user
        cursor, conn = open_db_history()
        '''
        cursor.execute("""
            SELECT 1 FROM wife_history
            WHERE date = ? AND wife_name = ? AND group_id = ?
            AND wife_type = 'ntr' AND user_id = ? AND target_id = ?
        """, (today, target_wife_name, group_id, target_id, user_id))
        '''
        cursor.execute("""
            SELECT 1 FROM wife_history
            WHERE date = ? AND wife_name = ? AND group_id = ?
            AND (wife_type IN ('gacha', 'exchange') AND user_id = ?)
        """, (today, target_wife_name, group_id, user_id))
        result = cursor.fetchone()
        # Close db
        conn.close()
        # Check if the wife is ntred from the user
        if not result:
            await bot.finish(ev, '对方的老婆不是你抽或换的哦', at_sender=True)
        # Check if the user already has a wife
        if str(user_id) in config:
            await bot.finish(ev, '你已经有了新老婆，过去的就让它过去吧',
                           at_sender=True)
    # 满足交换条件，添加进交换请求列表中
    exchange_manager.insert_exchange_request(group_id, user_id, target_id)
    if ntr_back:
        # 牛老婆次数减少2次
        limiters['ntr'].increase(f"{user_id}_{group_id}", 2)
        # 删除双方老婆信息，将他人老婆信息改成自己的
        config.pop(str(target_id), None)
        #config.pop(str(user_id), None)
        write_group_config(
                str(group_id), str(user_id), target_wife, today, config)
        await bot.send(ev, '牛头人必须死！你消耗2条命抢回了自己的老婆，并且对方没有获得补偿次数', at_sender=True)
    else:
        # 牛老婆次数减少1次
        limiters['ntr'].increase(f"{user_id}_{group_id}")
        if random.random() < ntr_possibility: 
            # JAG: Check new before write to db
            message = '你的阴谋已成功！对方补偿1次反牛机会'
            message += check_new(group_id, user_id, target_wife)
            # 删除双方老婆信息，将他人老婆信息改成自己的
            config.pop(str(target_id), None)
            #config.pop(str(user_id), None)
            write_group_config(
                    str(group_id), str(user_id), target_wife, today, config)
            # JAG: Ntr wife history
            write_db_history('ntr', user_id, target_id, group_id, 
                             target_wife.split('.')[0], today)
            limiters['ntr'].increase(f"{target_id}_{group_id}", -1)
            await bot.send(ev, message, at_sender=True)
        else:
            await bot.send(ev, f'你的阴谋失败了，黄毛被干掉了！你还有{daily_limits["ntr"] - limiters["ntr"].get_num(str(user_id) + "_" + str(group_id))}条命', at_sender=True)
    # 清除交换请求锁
    exchange_manager.remove_exchange_request(group_id, user_id, target_id)
    await asyncio.sleep(1)


# JAG: 牛老婆
@sv.on_rex(r'^(牛老婆)|(牛老婆)$')
async def ntr_wife(bot, ev: CQEvent):
    await ntr_wife_helper(bot, ev, ntr_back=False)


# JAG: 牛回本属于你的老婆
@sv.on_rex(r'^((md|妈的)?(和|跟)你爆了)|((md|妈的)?(和|跟)你爆了)$')
async def ntr_back_wife(bot, ev: CQEvent):
    await ntr_wife_helper(bot, ev, ntr_back=True)


# NTR开关文件路径
ntr_status_file = os.path.join(os.path.dirname(__file__), 
                               'config', 'ntr_status.json')
# 用来存储所有群组的NTR状态
ntr_statuses = {}

# 载入NTR状态
def load_ntr_statuses():
    global ntr_statuses
    # 检查文件是否存在
    if not os.path.exists(ntr_status_file):
        # 文件不存在，则创建空的状态文件
        with open(ntr_status_file, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
        ntr_statuses = {}
    else:
        # 文件存在，读取内容到ntr_statuses
        with open(ntr_status_file, 'r', encoding='utf-8') as f:
            ntr_statuses = json.load(f)

# 在程序启动时调用
load_ntr_statuses()


def save_ntr_statuses():
    with open(ntr_status_file, 'w', encoding='utf-8') as f:
        json.dump(ntr_statuses, f, ensure_ascii=False, indent=4)


@sv.on_fullmatch(("切换NTR开关状态", "切换ntr开关状态"))
async def switch_ntr(bot, ev: CQEvent):
    # 判断权限，只有用户为群管理员或为bot设置的超级管理员才能使用
    u_priv = priv.get_user_priv(ev)
    if u_priv < sv.manage_priv:
        return
    group_id = str(ev.group_id)
    
    # 取反群的NTR状态
    ntr_statuses[group_id] = not ntr_statuses.get(group_id, True)

    # 保存到文件
    save_ntr_statuses()

    load_ntr_statuses()
    # 提示信息
    await bot.send(ev, 'NTR功能已' + ('开启' if ntr_statuses[group_id] else '关闭'), at_sender=True)
    

########### 查看别人老婆 ##############
@sv.on_rex(r'^(查老婆)|(查老婆)$')
async def search_wife(bot, ev: CQEvent):
    # 获取QQ群、群用户QQ信息
    load_ntr_statuses()
    group_id = str(ev.group_id)
    target_id = None
    today = str(datetime.date.today())
    wife_name = None

    # 提取目标用户的QQ号
    for seg in ev.message:
        if seg.type == 'at' and seg.data['qq'] != 'all':
            target_id = int(seg.data['qq'])
            break

    # JAG: Check search limit if the user is querying other's wife
    if target_id:
        if not limiters['sc'].check(f"{ev.user_id}_{group_id}"):
            await bot.finish(ev,
                f'已达到每日查询上限（{daily_limits["sc"]}次）', at_sender=True)
        limiters['sc'].increase(f"{ev.user_id}_{group_id}")

    # 如果没指定就是自己
    target_id = target_id or str(ev.user_id)
    # 获取用户和目标用户的配置信息
    config = load_group_config(group_id)
    if config is not None:
        # Making sure we're comparing strings with strings,
        # or integers with integers
        if str(target_id) in config:  
            if config[str(target_id)][1] == today:
                wife_name = config[str(target_id)][0]
            else:
                await bot.finish(ev, '查询的老婆已过期', at_sender=True)
        else:
            await bot.finish(ev, '未找到老婆信息！', at_sender=True)
    else:
        await bot.finish(ev, '没有找到本群婚姻登记信息', at_sender=True)
    # 分割文件名和扩展名，只取图片名返回给用户
    name = wife_name.split('.')
    # 生成返回结果
    
    member_info = await bot.get_group_member_info(
            self_id=ev.self_id, group_id=ev.group_id, user_id=target_id)
    nick_name = member_info['card'] or member_info['nickname'] \
            or member_info['user_id'] or '未找到对方id'
    result = f'{str(nick_name)}的二次元老婆是{name[0]}哒~\n'

    try:
        # 尝试读取老婆图片，并添加到结果中
        wifeimg = R.img(f'wife/{wife_name}').cqcode
        # JAG: Show new info if the wife is new
        is_new = check_new(group_id, ev.user_id, wife_name)
        if is_new:
            result += str(wifeimg) + is_new
        # Otherwise, show mate info
        else:
            result += str(wifeimg) + check_mate(group_id, ev.user_id, wife_name)
    except Exception as e:
        hoshino.logger.error(f'读取老婆图片时发生错误{type(e)}')
        await bot.finish(ev, '读取老婆图片时发生错误', at_sender=True)

    # 发送消息
    await bot.send(ev,result,at_sender=True)


# JAG: 查询老婆历史记录
@sv.on_rex(r'^(老婆档案)|(老婆档案)$')
async def wife_stats(bot, ev: CQEvent):
    group_id = ev.group_id
    user_id = ev.user_id
    target_id = None
    for seg in ev.message:
        if seg.type == 'at' and seg.data['qq'] != 'all':
            target_id = int(seg.data['qq'])
            break
    user_id = target_id if target_id else user_id
    member_info = await bot.get_group_member_info(
            self_id=ev.self_id, group_id=ev.group_id, user_id=user_id)
    user_name = member_info['card'] or member_info['nickname'] \
            or member_info['user_id'] or '未找到对方id'
    # Open db
    cursor, conn = open_db_history()

    # 1. #wives collected
    cursor.execute("""
        SELECT COUNT(DISTINCT wife_name) FROM wife_history
        WHERE group_id = ? AND user_id = ?
    """, (group_id, user_id))
    result = cursor.fetchone()
    collected_count = result[0] if result else 0

    # 2. Total #wives
    total_count = len(os.listdir(imgpath))

    # 3. Total #gacha
    cursor.execute("""
        SELECT COUNT(*) FROM wife_history
        WHERE wife_type = 'gacha' AND group_id = ? AND user_id = ?
    """, (group_id, user_id))
    result = cursor.fetchone()
    gacha_count = result[0] if result else 0

    # 4. Most wife from gacha
    cursor.execute("""
        SELECT wife_name, COUNT(*) as cnt FROM wife_history
        WHERE wife_type = 'gacha' AND group_id = ? AND user_id = ?
        GROUP BY wife_name ORDER BY cnt DESC LIMIT 1
    """, (group_id, user_id))
    result = cursor.fetchone()
    most_gacha_wife = result[0] if result else '？？？'
    # 5. Most wife from gacha count
    most_gacha_wife_count = result[1] if result else 0

    # 6. #ntr
    cursor.execute("""
        SELECT COUNT(*) FROM wife_history
        WHERE wife_type = 'ntr' AND group_id = ? AND user_id = ?
    """, (group_id, user_id))
    result = cursor.fetchone()
    ntr_count = result[0] if result else 0

    # 7. Most ntr wife
    cursor.execute("""
        SELECT wife_name, COUNT(*) as cnt FROM wife_history
        WHERE wife_type = 'ntr' AND group_id = ? AND user_id = ?
        GROUP BY wife_name ORDER BY cnt DESC LIMIT 1
    """, (group_id, user_id))
    result = cursor.fetchone()
    most_ntr_wife = result[0] if result else '？？？'
    # 8. Most ntr wife count
    most_ntr_wife_count = result[1] if result else 0

    # 9. Most ntr user
    cursor.execute("""
        SELECT target_id, COUNT(*) as cnt FROM wife_history
        WHERE wife_type = 'ntr' AND group_id = ? AND user_id = ?
        GROUP BY target_id ORDER BY cnt DESC LIMIT 1
    """, (group_id, user_id))
    result = cursor.fetchone()
    if result:
        try:
            member_info = await bot.get_group_member_info(
                    self_id=ev.self_id, group_id=ev.group_id, user_id=result[0])
            most_ntr_user = member_info['card'] or member_info['nickname'] \
                    or member_info['user_id'] or '未找到对方id'
        except:
            # The member may no longer be in the group
            member_info = await bot.get_stranger_info(user_id=result[0])
            most_ntr_user = member_info['remark'] or member_info['nickname'] \
                    or member_info['user_id'] or '未找到对方id'
    else:
        most_ntr_user = '？？？'
    # 10. Most ntr user count
    most_ntr_user_count = result[1] if result else 0

    # 11. Most ntred wife
    cursor.execute("""
        SELECT wife_name, COUNT(*) as cnt FROM wife_history
        WHERE wife_type = 'ntr' AND group_id = ? AND target_id = ?
        GROUP BY wife_name ORDER BY cnt DESC LIMIT 1
    """, (group_id, user_id))
    result = cursor.fetchone()
    most_ntred_wife = result[0] if result else '？？？'
    # 12. Most ntred wife count
    most_ntred_wife_count = result[1] if result else 0

    # 13. Most ntred user
    cursor.execute("""
        SELECT user_id, COUNT(*) as cnt FROM wife_history
        WHERE wife_type = 'ntr' AND group_id = ? AND target_id = ?
        GROUP BY user_id ORDER BY cnt DESC LIMIT 1
    """, (group_id, user_id))
    result = cursor.fetchone()
    if result:
        try:
            member_info = await bot.get_group_member_info(
                    self_id=ev.self_id, group_id=ev.group_id, user_id=result[0])
            most_ntred_user = member_info['card'] or member_info['nickname'] \
                    or member_info['user_id'] or '未找到对方id'
        except:
            # The member may no longer be in the group
            member_info = await bot.get_stranger_info(user_id=result[0])
            most_ntred_user = member_info['remark'] or member_info['nickname'] \
                    or member_info['user_id'] or '未找到对方id'
    else:
        most_ntred_user = '？？？'
    # 14. Most ntred user count
    most_ntred_user_count = result[1] if result else 0

    # 15. #exchange
    cursor.execute("""
        SELECT COUNT(*) FROM wife_history
        WHERE wife_type = 'exchange' AND group_id = ? AND user_id = ?
    """, (group_id, user_id))
    exchange_count = cursor.fetchone()[0]

    # 16. Most exchange wife
    cursor.execute("""
        SELECT wife_name, COUNT(*) as cnt FROM wife_history 
        WHERE wife_type = 'exchange' AND group_id = ? AND user_id = ? 
        GROUP BY wife_name ORDER BY cnt DESC LIMIT 1
    """, (group_id, user_id))
    result = cursor.fetchone()
    most_exchange_wife = result[0] if result else '？？？'
    # 17. Most exchange wife count
    most_exchange_wife_count = result[1] if result else 0

    # 18. Most exchange user
    cursor.execute("""
        SELECT target_id, COUNT(*) as cnt FROM wife_history
        WHERE wife_type = 'exchange' AND group_id = ? AND user_id = ?
        GROUP BY target_id ORDER BY cnt DESC LIMIT 1
    """, (group_id, user_id))
    result = cursor.fetchone()
    if result:
        try:
            member_info = await bot.get_group_member_info(
                    self_id=ev.self_id, group_id=ev.group_id, user_id=result[0])
            most_exchange_user = member_info['card'] \
                    or member_info['nickname'] or member_info['user_id'] \
                    or '未找到对方id'
        except:
            # The member may no longer be in the group
            member_info = await bot.get_stranger_info(user_id=result[0])
            most_exchange_user = member_info['remark'] \
                    or member_info['nickname'] or member_info['user_id'] \
                    or '未找到对方id'
    else:
        most_exchange_user = '？？？'
    # 19. Most exchange user count
    most_exchange_user_count = result[1] if result else 0

    # 20. Total #wife divorced
    cursor.execute("""
        SELECT COUNT(*) FROM wife_history
        WHERE wife_type = 'divorce' AND group_id = ? AND user_id = ?
    """, (group_id, user_id))
    result = cursor.fetchone()
    divorce_count = result[0] if result else 0

    # 21. Most wife divorced
    cursor.execute("""
        SELECT wife_name, COUNT(*) as cnt FROM wife_history
        WHERE wife_type = 'divorce' AND group_id = ? AND user_id = ?
        GROUP BY wife_name ORDER BY cnt DESC LIMIT 1
    """, (group_id, user_id))
    result = cursor.fetchone()
    most_divorce_wife = result[0] if result else '？？？'
    # 22. Most divorced wife count
    most_divorce_wife_count = result[1] if result else 0

    # 23. Total #wife mated
    cursor.execute("""
        SELECT COUNT(*) FROM wife_history
        WHERE wife_type = 'mate' AND group_id = ? AND user_id = ?
    """, (group_id, user_id))
    result = cursor.fetchone()
    mate_count = result[0] if result else 0

    # 24. Most wife mated
    cursor.execute("""
        SELECT wife_name, COUNT(*) as cnt FROM wife_history
        WHERE wife_type = 'mate' AND group_id = ? AND user_id = ?
        GROUP BY wife_name ORDER BY cnt DESC LIMIT 1
    """, (group_id, user_id))
    result = cursor.fetchone()
    most_mate_wife = result[0] if result else '？？？'
    # 25. Most mated wife count
    most_mate_wife_count = result[1] if result else 0

    # Close db
    #conn.commit()
    conn.close()

    ret = f'@{user_name}的老婆档案：\n'
    ret += f'- 总共解锁的老婆：{collected_count}/{total_count}位\n'
    ret += f'- 总共抽过的老婆：{gacha_count}次\n'
    ret += f'- 抽到最多的老婆：{most_gacha_wife}({most_gacha_wife_count}次)\n'
    ret += f'- 总共离过的老婆：{divorce_count}次\n'
    ret += f'- 离婚最多的老婆：{most_divorce_wife}({most_divorce_wife_count}次)\n'
    ret += f'- 总共牛过的老婆：{ntr_count}次\n'
    ret += f'- 最喜欢牛的老婆：{most_ntr_wife}({most_ntr_wife_count}次)\n'
    ret += f'- 最喜欢牛的群友：@{most_ntr_user}({most_ntr_user_count}次)\n'
    ret += f'- 被牛最多的老婆：{most_ntred_wife}({most_ntred_wife_count}次)\n'
    ret += f'- 被牛最多的群友：@{most_ntred_user}({most_ntred_user_count}次)\n'
    ret += f'- 总共日过的老婆：{mate_count}次\n'
    ret += f'- 最喜欢日的老婆：{most_mate_wife}({most_mate_wife_count}次)\n'
    ret += f'- 总共换过的老婆：{exchange_count}次\n'
    ret += f'- 最喜欢换的老婆：{most_exchange_wife}({most_exchange_wife_count}次)\n'
    ret += f'- 最喜欢换的群友：@{most_exchange_user}({most_exchange_user_count}次)'

    await bot.send(ev, ret, at_sender=False)

# JAG: 复活被牛走的老婆
@sv.on_fullmatch('复活吧我的爱人')
async def animewife(bot, ev: CQEvent):
    # Get group_id, user_id and today's date
    group_id = ev.group_id
    user_id = ev.user_id
    today = str(datetime.date.today())
    # Load group config
    config = load_group_config(group_id)
    # Check if the user has a wife today
    if config is not None and str(user_id) in list(config) \
            and config[str(user_id)][1] == today:
        await bot.finish(ev, '你已经有老婆了哦', at_sender=True)
    cursor, conn = open_db_history()
    cursor.execute("""
        SELECT wife_name FROM wife_history WHERE date = ? AND group_id = ? 
        AND user_id = ? AND wife_type IN ('gacha', 'exchange')
        ORDER BY id DESC LIMIT 1;
    """, (today, group_id, user_id))
    result = cursor.fetchone()
    # Close db
    conn.close()
    # Check if the user has a wife from gacha or exchange
    if result:
        wife_name = result[0] + '.jpg'
        write_group_config(group_id, user_id, wife_name, today, config)
        await bot.send(ev, '复活吧！我的爱人！', at_sender=True)
    else:
        await bot.send(ev, '你没有老婆可以复活', at_sender=True)


# 每行显示的老婆数量
COL_NUM = 10
img_cache = {}

# 老婆图鉴
# Modified from https://github.com/Rlezzo/WifeGacha/blob/master/main.py
@sv.on_rex(r'^(老婆图鉴)|(老婆图鉴)$')
async def wife_atlas(bot, ev: CQEvent):
    # 获取QQ群、群用户QQ信息
    group_id = ev.group_id
    user_id = ev.user_id
    target_id = None

    # 提取目标用户的QQ号
    for seg in ev.message:
        if seg.type == 'at' and seg.data['qq'] != 'all':
            target_id = int(seg.data['qq'])
            break

    # 获取用户昵称
    user_id = target_id if target_id else user_id
    member_info = await bot.get_group_member_info(
            self_id=ev.self_id, group_id=ev.group_id, user_id=user_id)
    user_name = member_info['card'] or member_info['nickname'] \
            or member_info['user_id'] or '未找到对方id'

    # Open db
    cursor, conn = open_db_history()
    cursor.execute("""
        SELECT DISTINCT wife_name FROM wife_history
        WHERE group_id = ? AND user_id = ?
    """, (group_id, user_id))
    result = cursor.fetchall()
    # Return all the unique wives
    unique_wives = [wife[0] for wife in result] if result else []
    conn.close()
    # 获取用户解锁的老婆
    drawn_wives_count = len(unique_wives)

    # 获取老婆总数
    wives_names = [f for f in os.listdir(imgpath) if '.' in f]
    total_wives_count = len(wives_names)
    len_card = total_wives_count

    # 计算行数
    row_num = len_card // COL_NUM if len_card % COL_NUM != 0 \
            else len_card // COL_NUM - 1
    # 得到背景图片
    base_img_path = os.path.join(
            os.path.dirname(__file__), 'config', 'frame.png')
    base_img = Image.open(base_img_path)
    # 调整图像大小:
    base_img = base_img.resize((40 + COL_NUM * 80 + (COL_NUM - 1) * 10, 
                                150 + row_num * 80 + (row_num - 1) * 10),
                                Image.ANTIALIAS)
    # 初始化行索引偏移和行偏移:
    row_index_offset, row_offset = 0, 0

    # 卡片文件名列表:
    for index, wife_name in enumerate(wives_names):
        row_index = index // COL_NUM + row_index_offset
        col_index = index % COL_NUM
        # Open image
        image_name = os.path.join(imgpath, wife_name)
        # Save the processed 80*80 image to cache
        if image_name not in img_cache:
            sign_image = Image.open(image_name)
            # 图片被缩放到80x80像素，并应用抗锯齿算法
            sign_image = sign_image.resize((80, 80), Image.ANTIALIAS)
            img_cache[image_name] = sign_image
        else:
            sign_image = img_cache[image_name]
        # 如果老婆不在用户解锁的老婆列表中，则转换为灰度图像
        if wife_name.split('.')[0] not in unique_wives:
            sign_image = sign_image.convert('L')
        base_img.paste(sign_image, (
            30 + col_index * 80 + (col_index - 1) * 10,
            row_offset + 40 + row_index * 80 + (row_index - 1) * 10))

    row_offset += 30
    buf = BytesIO()
    base_img = base_img.convert('RGB')
    base_img.save(buf, format='JPEG')
    base64_str = f'base64://{base64.b64encode(buf.getvalue()).decode()}'
    messages = f'@{user_name}的老婆图鉴：'
    messages += f'\n[CQ:image,file={base64_str}]'
    messages += f'\n图鉴完成度: {drawn_wives_count} / {total_wives_count}'

    await bot.send(ev, messages, at_sender=False)


@sv.on_fullmatch('离婚')
async def divorce_wife(bot, ev: CQEvent):
    # 获取QQ群、群用户QQid
    group_id = ev.group_id
    user_id = ev.user_id
    # 获取今天的日期，转换为字符串格式
    today = str(datetime.date.today())
    # 载入群组信息
    config = load_group_config(group_id)

    # Regular checks, the same as in search_wife()
    if config is None:
        await bot.finish(ev, '没有找到本群婚姻登记信息', at_sender=True)
    if str(user_id) not in config:
        await bot.finish(ev, '未找到老婆信息！', at_sender=True)
    if config[str(user_id)][1] != today:
        await bot.finish(ev, '你的老婆已过期', at_sender=True)
    # JAG: Check reset limit
    if not limiters['div'].check(f"{user_id}_{group_id}"):
        await bot.finish(ev,
            f'为防止渣男泛滥，一天最多可离婚{daily_limits["div"]}次',
            at_sender=True)
    # 检查发起者或目标者是否已经在任何交换中
    if not exchange_manager.is_eligible_for_exchange(
            group_id, user_id, user_id):
        await bot.finish(ev, '双方有人正在进行换妻play中，请稍后再试',
                       at_sender=True)
    # 满足交换条件，添加进交换请求列表中
    exchange_manager.insert_exchange_request(group_id, user_id, user_id)

    # JAG: Start divorce
    limiters['div'].increase(f"{user_id}_{group_id}")

    # 删除用户的老婆信息
    wife_name = config[str(user_id)][0]
    wife_name = wife_name.split('.')[0]
    config.pop(str(user_id), None)
    write_group_config(group_id, user_id, None, None, config)

    # JAG: Write divorce history to db
    write_db_history('divorce', user_id, 0, group_id, wife_name, today)

    await bot.send(ev, f'你与{wife_name}解除婚姻成功', at_sender=True)
    # 清除交换请求锁
    exchange_manager.remove_exchange_request(group_id, user_id, user_id)


@sv.on_rex(r'^(日老婆)|(日老婆)$')
async def mate_wife(bot, ev: CQEvent):
    # 获取QQ群、群用户QQid
    group_id = ev.group_id
    user_id = ev.user_id
    # JAG: Initialize target_id and is_target
    target_id = user_id
    is_target = False
    # 获取今天的日期，转换为字符串格式
    today = str(datetime.date.today())
    # 载入群组信息
    config = load_group_config(group_id)

    for seg in ev.message:
        if seg.type == 'at' and seg.data['qq'] != 'all':
            target_id = int(seg.data['qq'])
            is_target = True
            break

    # Regular checks, the same as in search_wife()
    if config is None:
        await bot.finish(ev, '没有找到本群婚姻登记信息', at_sender=True)
    if str(target_id) not in config:
        await bot.finish(ev, '未找到老婆信息！', at_sender=True)
    
    if config[str(target_id)][1] != today:
        await bot.finish(ev, '该老婆已过期', at_sender=True)

    # Get wife name
    wife_name = config[str(target_id)][0]
    wife_name = wife_name.split('.')[0]

    # JAG: If mating someone else's wife
    if is_target:
        if check_new(group_id, user_id, wife_name):
            await bot.finish(ev, '你还没有这位老婆哦，先去解锁图鉴吧！',
                             at_sender=True)
        # JAG: Need to check mate limit first otherwise there will be a bug
        if not limiters['mate'].check(f"{user_id}_{group_id}") \
                or daily_limits["mate"] - limiters["mate"].get_num(
                f"{user_id}_{group_id}") < 2:
            await bot.finish(ev, f'你需要2条命来触发寝取', at_sender=True)
        limiters['mate'].increase(f"{user_id}_{group_id}", 2)
    # JAG: If mating own wife
    else:
        # Check mate limit
        if not limiters['mate'].check(f"{user_id}_{group_id}"):
            await bot.finish(ev,
                f'劲酒虽好，可不要贪杯哦。一天最多可日{daily_limits["mate"]}次',
                at_sender=True)
        limiters['mate'].increase(f"{user_id}_{group_id}")

    # JAG: Write mate history to db
    write_db_history('mate', user_id, target_id, group_id, wife_name, today)

    if is_target:
        # Find target's name
        member_info = await bot.get_group_member_info(
                self_id=ev.self_id, group_id=ev.group_id, user_id=target_id)
        nick_name = member_info['card'] or member_info['nickname'] \
                or member_info['user_id'] or '未找到对方id'
        await bot.send(ev, f'你消耗2条命，瞒着{str(nick_name)}偷偷与{wife_name}进行了深入交流，好感度+1', at_sender=True)
    else:
        await bot.send(ev, f'你与{wife_name}进行了深入交流，好感度+1', 
                       at_sender=True)





