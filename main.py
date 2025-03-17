import random
import yaml
import os
import re
import time
import json
import sys
from astrbot.api.all import *
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from niuniu_shop import NiuniuShop
from niuniu_games import NiuniuGames

# 常量定义
PLUGIN_DIR = os.path.join('data', 'plugins', 'astrbot_plugin_niuniu')
os.makedirs(PLUGIN_DIR, exist_ok=True)
NIUNIU_LENGTHS_FILE = os.path.join('data', 'niuniu_lengths.yml')
NIUNIU_TEXTS_FILE = os.path.join(PLUGIN_DIR, 'niuniu_game_texts.yml')
LAST_ACTION_FILE = os.path.join(PLUGIN_DIR, 'last_actions.yml')

@register("niuniu_plugin", "长安某", "牛牛插件，包含注册牛牛、打胶、我的牛牛、比划比划、牛牛排行等功能", "3.4.2")
class NiuniuPlugin(Star):
    # 冷却时间常量（秒）
    COOLDOWN_10_MIN = 600    # 10分钟
    COOLDOWN_30_MIN = 1800   # 30分钟
    COMPARE_COOLDOWN = 300   # 比划冷却
    INVITE_LIMIT = 3         # 邀请次数限制

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.niuniu_lengths = self._load_niuniu_lengths()
        self.niuniu_texts = self._load_niuniu_texts()
        self.last_dajiao_time = {}      # {str(group_id): {str(user_id): last_time}}
        self.last_compare_time = {}     # {str(group_id): {str(user_id): {str(target_id): last_time}}}
        self.last_actions = self._load_last_actions()
        self.admins = self._load_admins()  # 加载管理员列表
        self.shop = NiuniuShop(self)  # 实例化商城模块
        self.games = NiuniuGames(self)  # 实例化游戏模块
    # region 数据管理
    def _create_niuniu_lengths_file(self):
        """创建数据文件"""
        try:
            with open(NIUNIU_LENGTHS_FILE, 'w', encoding='utf-8') as f:
                yaml.dump({}, f)
        except Exception as e:
            self.context.logger.error(f"创建文件失败: {str(e)}")

    def _load_niuniu_lengths(self):
        """加载牛牛数据"""
        if not os.path.exists(NIUNIU_LENGTHS_FILE):
            self._create_niuniu_lengths_file()
        
        try:
            with open(NIUNIU_LENGTHS_FILE, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            # 数据结构验证
            for group_id in list(data.keys()):
                group_data = data[group_id]
                if not isinstance(group_data, dict):
                    data[group_id] = {'plugin_enabled': False}
                elif 'plugin_enabled' not in group_data:
                    group_data['plugin_enabled'] = False
                for user_id in list(group_data.keys()):
                    user_data = group_data[user_id]
                    if isinstance(user_data, dict):
                        user_data.setdefault('coins', 0)
                        user_data.setdefault('items', {}) 
            return data
        except Exception as e:
            self.context.logger.error(f"加载数据失败: {str(e)}")
            return {}
    def _load_niuniu_texts(self):
        """加载游戏文本"""
        default_texts = {
            'register': {
                'success': "🧧 {nickname} 成功注册牛牛！\n📏 初始长度：{length}cm\n💪 硬度等级：{hardness}",
                'already_registered': "⚠️ {nickname} 你已经注册过牛牛啦！",
            },
            'dajiao': {
                'cooldown': [
                    "⏳ {nickname} 牛牛需要休息，{remaining}分钟后可再打胶",
                    "🛑 冷却中，{nickname} 请耐心等待 (＞﹏＜)"
                ],
                'increase': [
                    "🚀 {nickname} 打胶成功！长度增加 {change}cm！",
                    "🎉 {nickname} 的牛牛茁壮成长！+{change}cm"
                ],
                'decrease': [
                    "😱 {nickname} 用力过猛！长度减少 {change}cm！",
                    "⚠️ {nickname} 操作失误！-{change}cm"
                ],
                'decrease_30min': [
                    "😱 {nickname} 用力过猛！长度减少 {change}cm！",
                    "⚠️ {nickname} 操作失误！-{change}cm"
                ],
                'no_effect': [
                    "🌀 {nickname} 的牛牛毫无变化...",
                    "🔄 {nickname} 这次打胶没有效果"
                ],
                'not_registered': "❌ {nickname} 请先注册牛牛"
            },
            'my_niuniu': {
                'info': "📊 {nickname} 的牛牛状态\n📏 长度：{length}\n💪 硬度：{hardness}\n📝 评价：{evaluation}",
                'evaluation': {
                    'short': ["小巧玲珑", "精致可爱"],
                    'medium': ["中规中矩", "潜力无限"],
                    'long': ["威风凛凛", "傲视群雄"],
                    'very_long': ["擎天巨柱", "突破天际"],
                    'super_long': ["超级长", "无与伦比"],
                    'ultra_long': ["超越极限", "无人能敌"]
                },
                'not_registered': "❌ {nickname} 请先注册牛牛"
            },
            'compare': {
                'no_target': "❌ {nickname} 请指定比划对象",
                'target_not_registered': "❌ 对方尚未注册牛牛",
                'cooldown': "⏳ {nickname} 请等待{remaining}分钟后再比划",
                'self_compare': "❌ 不能和自己比划",
                'win': [
                    "🎉 {winner} 战胜了 {loser}！\n📈 增加 {gain}cm",
                    "🏆 {winner} 的牛牛更胜一筹！+{gain}cm"
                ],
                'lose': [
                    "😭 {loser} 败给 {winner}\n📉 减少 {loss}cm",
                    "💔 {loser} 的牛牛不敌对方！-{loss}cm"
                ],
                'draw': "🤝 双方势均力敌！",
                'double_loss': "😱 {nickname1} 和 {nickname2} 的牛牛因过于柔软发生缠绕，长度减半！",
                'hardness_win': "🎉 {nickname} 因硬度优势获胜！",
                'hardness_lose': "💔 {nickname} 因硬度劣势败北！",
                'user_no_increase': "😅 {nickname} 的牛牛没有任何增长。"
            },
            'ranking': {
                'header': "🏅 牛牛排行榜 TOP10：\n",
                'no_data': "📭 本群暂无牛牛数据",
                'item': "{rank}. {name} ➜ {length}"
            },
            'menu': {
                'default': """📜 牛牛菜单：
🔹 注册牛牛 - 初始化你的牛牛
🔹 打胶 - 提升牛牛长度
🔹 我的牛牛 - 查看当前状态
🔹 比划比划 @目标 - 发起对决
🔹 牛牛排行 - 查看群排行榜
🔹 牛牛开/关 - 管理插件"""
            },
            'system': {
                'enable': "✅ 牛牛插件已启用",
                'disable': "❌ 牛牛插件已禁用"
            }
        }
        
        try:
            if os.path.exists(NIUNIU_TEXTS_FILE):
                with open(NIUNIU_TEXTS_FILE, 'r', encoding='utf-8') as f:
                    custom_texts = yaml.safe_load(f) or {}
                    return self._deep_merge(default_texts, custom_texts)
        except Exception as e:
            self.context.logger.error(f"加载文本失败: {str(e)}")
        return default_texts

    def _deep_merge(self, base, update):
        """深度合并字典"""
        for key, value in update.items():
            if isinstance(value, dict):
                base[key] = self._deep_merge(base.get(key, {}), value)
            else:
                base[key] = value
        return base

    def _save_niuniu_lengths(self):
        """保存数据"""
        try:
            with open(NIUNIU_LENGTHS_FILE, 'w', encoding='utf-8') as f:
                yaml.dump(self.niuniu_lengths, f, allow_unicode=True)
        except Exception as e:
            self.context.logger.error(f"保存失败: {str(e)}")

    def _load_last_actions(self):
        """加载冷却数据"""
        try:
            with open(LAST_ACTION_FILE, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except:
            return {}

    def _save_last_actions(self):
        """保存冷却数据"""
        try:
            with open(LAST_ACTION_FILE, 'w', encoding='utf-8') as f:
                yaml.dump(self.last_actions, f, allow_unicode=True)
        except Exception as e:
            self.context.logger.error(f"保存冷却数据失败: {str(e)}")

    def _load_admins(self):
        """加载管理员列表"""
        try:
            with open(os.path.join('data', 'cmd_config.json'), 'r', encoding='utf-8-sig') as f:
                config = json.load(f)
                return config.get('admins_id', [])
        except Exception as e:
            self.context.logger.error(f"加载管理员列表失败: {str(e)}")
            return []

    def is_admin(self, user_id):
        """检查用户是否为管理员"""
        return str(user_id) in self.admins
    # endregion

    # region 工具方法
    def format_length(self, length):
        """格式化长度显示"""
        if length >= 100:
            return f"{length/100:.2f}m"
        return f"{length}cm"

    def get_group_data(self, group_id):
        """获取群组数据"""
        group_id = str(group_id)
        if group_id not in self.niuniu_lengths:
            self.niuniu_lengths[group_id] = {'plugin_enabled': False}  # 默认关闭插件
        return self.niuniu_lengths[group_id]

    def get_user_data(self, group_id, user_id):
        """获取用户数据"""
        group_data = self.get_group_data(group_id)
        user_id = str(user_id)
        return group_data.get(user_id)

    def check_cooldown(self, last_time, cooldown):
        """检查冷却时间"""
        current = time.time()
        elapsed = current - last_time
        remaining = cooldown - elapsed
        return remaining > 0, remaining

    def parse_at_target(self, event):
        """解析@目标"""
        for comp in event.message_obj.message:
            if isinstance(comp, At):
                return str(comp.qq)
        return None

    def parse_target(self, event):
        """解析@目标或用户名"""
        for comp in event.message_obj.message:
            if isinstance(comp, At):
                return str(comp.qq)
        msg = event.message_str.strip()
        if msg.startswith("比划比划"):
            target_name = msg[len("比划比划"):].strip()
            if target_name:
                group_id = str(event.message_obj.group_id)
                group_data = self.get_group_data(group_id)
                for user_id, user_data in group_data.items():
                    if isinstance(user_data, dict): 
                        nickname = user_data.get('nickname', '')
                        if re.search(re.escape(target_name), nickname, re.IGNORECASE):
                            return user_id
        return None
    # endregion

    # region 事件处理
    niuniu_commands = ["牛牛菜单", "牛牛开", "牛牛关", "注册牛牛", "打胶", "我的牛牛", "比划比划", "牛牛排行"]

    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """群聊消息处理器"""
        group_id = str(event.message_obj.group_id)
        group_data = self.get_group_data(group_id)

        msg = event.message_str.strip()
        if msg.startswith("牛牛开"):
            async for result in self._toggle_plugin(event, True):
                yield result
            return
        elif msg.startswith("牛牛关"):
            async for result in self._toggle_plugin(event, False):
                yield result
            return
        elif msg.startswith("牛牛菜单"):
            async for result in self._show_menu(event):
                yield result
            return
        # 如果插件未启用，忽略其他所有消息
        if not group_data.get('plugin_enabled', False):
            return
        # 处理其他命令
        if msg.startswith("开冲"):
            async for result in self.games.start_rush(event):
                yield result
        elif msg.startswith("停止开冲"):
            async for result in self.games.stop_rush(event):
                yield result
        elif msg.startswith("飞飞机"):
            async for result in self.games.fly_plane(event):
                yield result
        elif msg.startswith("我的牛牛"):
            async for result in self._show_status(event):
                yield result
        elif msg.startswith("牛牛排行"):
            async for result in self._show_ranking(event):
                yield result
        elif msg.startswith("牛牛商城"):
            async for result in self.shop.show_shop(event):
                yield result                
        elif msg.startswith("牛牛背包"):
            async for result in self.shop.show_items(event):
                yield result                
        else:
            # 处理其他命令
            handler_map = {
                "注册牛牛": self._register,
                "打胶": self._dajiao,
                # "我的牛牛": self._show_status,
                "比划比划": self._compare,
                # "牛牛排行": self._show_ranking,
                # "牛牛商城": self.shop.show_shop,
                "牛牛购买": self.shop.handle_buy,
                # "牛牛背包": self.shop.show_items
            }

            for cmd, handler in handler_map.items():
                if msg.startswith(cmd):
                    # 检查是否正在开冲
                    user_id = str(event.get_sender_id())
                    user_data = self.get_user_data(group_id, user_id)
                    if user_data and user_data.get('is_rushing', False):
                        yield event.plain_result("❌ 牛牛快冲晕了，还做不了其他事情，要不先停止开冲？")
                        return
                    async for result in handler(event):
                        yield result
                    return
    @event_message_type(EventMessageType.PRIVATE_MESSAGE)
    async def on_private_message(self, event: AstrMessageEvent):
        """私聊消息处理器"""
        msg = event.message_str.strip()
        niuniu_commands = [
            "牛牛菜单", "牛牛开", "牛牛关", "注册牛牛", "打胶", "我的牛牛",
            "比划比划", "牛牛排行", "牛牛商城", "牛牛购买", "牛牛背包",
            "开冲", "停止开冲", "飞飞机"  
        ]
        
        if any(msg.startswith(cmd) for cmd in niuniu_commands):
            yield event.plain_result("不许一个人偷偷玩牛牛")
        else:
            return
    async def _toggle_plugin(self, event, enable):
        """开关插件"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())

        # 检查是否为管理员
        if not self.is_admin(user_id):
            yield event.plain_result("❌ 只有管理员才能使用此指令")
            return

        self.get_group_data(group_id)['plugin_enabled'] = enable
        self._save_niuniu_lengths()
        text_key = 'enable' if enable else 'disable'
        yield event.plain_result(self.niuniu_texts['system'][text_key])

    async def _register(self, event):
        """注册牛牛"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()

        group_data = self._load_niuniu_lengths().get(group_id, {'plugin_enabled': False})
        if not group_data.get('plugin_enabled', False):
            yield event.plain_result("❌ 插件未启用")
            return

        if user_id in group_data:
            text = self.niuniu_texts['register']['already_registered'].format(nickname=nickname)
            yield event.plain_result(text)
            return

        cfg = self.config.get('niuniu_config', {})
        group_data[user_id] = {
            'nickname': nickname,
            'length': random.randint(cfg.get('min_length', 3), cfg.get('max_length', 10)),
            'hardness': 1,
            'coins': 0,
            'items': {}
        }
        self.niuniu_lengths[group_id] = group_data
        self._save_niuniu_lengths()

        text = self.niuniu_texts['register']['success'].format(
            nickname=nickname,
            length=group_data[user_id]['length'],
            hardness=group_data[user_id]['hardness']
        )
        yield event.plain_result(text)

    async def _dajiao(self, event: AstrMessageEvent):
        """打胶功能"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()

        group_data = self._load_niuniu_lengths().get(group_id, {'plugin_enabled': False})
        if not group_data.get('plugin_enabled', False):
            yield event.plain_result("❌ 插件未启用")
            return

        user_data = self.get_user_data(group_id, user_id)
        if not user_data:
            text = self.niuniu_texts['dajiao']['not_registered'].format(nickname=nickname)
            yield event.plain_result(text)
            return

        user_items = self.shop.get_user_items(group_id, user_id)
        has_zhiming_rhythm = user_items.get("致命节奏", 0) > 0
        last_time = self.last_actions.setdefault(group_id, {}).get(user_id, {}).get('dajiao', 0)
        
        # 初始化消息容器
        result_msg = []
        
        # 检查是否处于冷却期
        on_cooldown, remaining = self.check_cooldown(last_time, self.COOLDOWN_10_MIN)
        
        # 只有在冷却期内且持有道具时才触发效果
        if on_cooldown and has_zhiming_rhythm:
            # 消耗道具并跳过冷却
            self.shop.consume_item(group_id, user_id, "致命节奏")
            result_msg.append(f"⚡ 触发致命节奏！{nickname} 无视冷却强行打胶！")
            elapsed = self.COOLDOWN_30_MIN + 1  # 强制进入增益逻辑
        else:
            # 原有冷却处理
            if on_cooldown and not has_zhiming_rhythm:
                mins = int(remaining // 60) + 1
                text = random.choice(self.niuniu_texts['dajiao']['cooldown']).format(
                    nickname=nickname, remaining=mins
                )
                yield event.plain_result(text)
                return
            elapsed = time.time() - last_time

        # 计算变化
        change = 0
        current_time = time.time()

        if elapsed < self.COOLDOWN_30_MIN:  # 10-30分钟
            rand = random.random()
            if rand < 0.4:   # 40% 增加
                change = random.randint(2, 5)
            elif rand < 0.7: # 30% 减少
                change = -random.randint(1, 3)
                template = random.choice(self.niuniu_texts['dajiao']['decrease'])
        else:  # 30分钟后
            rand = random.random()
            if rand < 0.8:  # 80% 增加
                change = random.randint(3, 6)
                user_data['hardness'] = min(user_data['hardness'] + 1, 10)
            # elif rand < 0.9: # 10% 减少
            #     change = -random.randint(1, 1)
            #     template = random.choice(self.niuniu_texts['dajiao']['decrease_30min'])

        # 应用变化
        user_data['length'] = max(1, user_data['length'] + change)
        self.last_actions.setdefault(group_id, {}).setdefault(user_id, {})['dajiao'] = current_time
        self._save_last_actions()
        self._save_niuniu_lengths()

        # 生成消息
        if change > 0:
            template = random.choice(self.niuniu_texts['dajiao']['increase'])
        elif change < 0:
            template = template  
        else:
            template = random.choice(self.niuniu_texts['dajiao']['no_effect'])

        text = template.format(nickname=nickname, change=abs(change))
        
        # 合并提示消息
        if result_msg:
            final_text = "\n".join(result_msg + [text])
        else:
            final_text = text
            
        yield event.plain_result(f"{final_text}\n当前长度：{self.format_length(user_data['length'])}")
    async def _compare(self, event):
        """比划功能"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()

        group_data = self._load_niuniu_lengths().get(group_id, {'plugin_enabled': False})
        if not group_data.get('plugin_enabled', False):
            yield event.plain_result("❌ 插件未启用")
            return

        # 获取自身数据
        user_data = self.get_user_data(group_id, user_id)
        if not user_data:
            yield event.plain_result(self.niuniu_texts['dajiao']['not_registered'].format(nickname=nickname))
            return

        # 解析目标
        target_id = self.parse_target(event)
        if not target_id:
            yield event.plain_result(self.niuniu_texts['compare']['no_target'].format(nickname=nickname))
            return
        
        if target_id == user_id:
            yield event.plain_result(self.niuniu_texts['compare']['self_compare'])
            return

        # 获取目标数据
        target_data = self.get_user_data(group_id, target_id)
        if not target_data:
            yield event.plain_result(self.niuniu_texts['compare']['target_not_registered'])
            return

        # 冷却检查
        compare_records = self.last_compare_time.setdefault(group_id, {}).setdefault(user_id, {})
        last_compare = compare_records.get(target_id, 0)
        on_cooldown, remaining = self.check_cooldown(last_compare, self.COMPARE_COOLDOWN)
        if on_cooldown:
            mins = int(remaining // 60) + 1
            text = self.niuniu_texts['compare']['cooldown'].format(
                nickname=nickname,
                remaining=mins
            )
            yield event.plain_result(text)
            return

        # 检查10分钟内比划次数
        compare_records = self.last_compare_time.setdefault(group_id, {}).setdefault(user_id, {})
        last_compare_time = compare_records.get('last_time', 0)
        current_time = time.time()

        # 如果超过10分钟，重置计数
        if current_time - last_compare_time > 600:
            compare_records['count'] = 0
            compare_records['last_time'] = current_time  # 更新最后比划时间

        compare_count = compare_records.get('count', 0)

        if compare_count >= 3:
            yield event.plain_result("❌ 5分钟内只能比划三次")
            return

        # 更新冷却时间和比划次数
        compare_records[target_id] = current_time
        compare_records['count'] = compare_count + 1

        # 检查是否持有夺心魔蝌蚪罐头
        user_items = self.shop.get_user_items(group_id, user_id)
        if user_items.get("夺心魔蝌蚪罐头", 0) > 0:
            # 随机决定效果
            effect_chance = random.random()
            if effect_chance < 0.5:  # 50%的概率夺取对方全部长度
                original_target_length = target_data['length']
                user_data['length'] += original_target_length
                target_data['length'] = 1
                result_msg = [
                    "⚔️ 【牛牛对决结果】 ⚔️",
                    f"🎉 {nickname} 获得了夺心魔技能，夺取了 {target_data['nickname']} 的全部长度！",
                    f"🗡️ {nickname}: {self.format_length(user_data['length'] - original_target_length)} → {self.format_length(user_data['length'])}",
                    f"🛡️ {target_data['nickname']}: {self.format_length(original_target_length)} → 1cm"
                ]
                self.shop.consume_item(group_id, user_id, "夺心魔蝌蚪罐头")
                self._save_niuniu_lengths()
                yield event.plain_result("\n".join(result_msg))
                return
            elif effect_chance < 0.6:  # 10%的概率清空自己的长度
                original_user_length = user_data['length']
                user_data['length'] = 1
                result_msg = [
                    "⚔️ 【牛牛对决结果】 ⚔️",
                    f"💔 {nickname} 使用夺心魔蝌蚪罐头，牛牛变成了夺心魔！！！",
                    f"🗡️ {nickname}: {self.format_length(original_user_length)} → 1cm",
                    f"🛡️ {target_data['nickname']}: {self.format_length(target_data['length'])}"
                ]
                self.shop.consume_item(group_id, user_id, "夺心魔蝌蚪罐头")
                self._save_niuniu_lengths()
                yield event.plain_result("\n".join(result_msg))
                return
            else:  # 40%的概率无效
                result_msg = [
                    "⚔️ 【牛牛对决结果】 ⚔️",
                    f"⚠️ {nickname} 使用夺心魔蝌蚪罐头，但是罐头好像坏掉了...",
                    f"🗡️ {nickname}: {self.format_length(user_data['length'])}",
                    f"🛡️ {target_data['nickname']}: {self.format_length(target_data['length'])}"
                ]
                self.shop.consume_item(group_id, user_id, "夺心魔蝌蚪罐头")
                self._save_niuniu_lengths()
                yield event.plain_result("\n".join(result_msg))
                return

        # 计算胜负
        u_len = user_data['length']
        t_len = target_data['length']
        u_hardness = user_data['hardness']
        t_hardness = target_data['hardness']

        # 基础胜率
        base_win = 0.5

        # 长度影响（最多影响20%的胜率）
        length_factor = (u_len - t_len) / max(u_len, t_len) * 0.2

        # 硬度影响（最多影响10%的胜率）
        hardness_factor = (u_hardness - t_hardness) * 0.05

        # 最终胜率（限制在20%-80%之间）
        win_prob = min(max(base_win + length_factor + hardness_factor, 0.2), 0.8)

        # 记录比划前的长度
        old_u_len = user_data['length']
        old_t_len = target_data['length']

        # 执行判定
        if random.random() < win_prob:
            gain = random.randint(0, 10)
            loss = random.randint(1, 9)
            user_data['length'] += gain
            target_data['length'] = max(1, target_data['length'] - loss)
            text = random.choice(self.niuniu_texts['compare']['win']).format(
                nickname=nickname,
                target_nickname=target_data['nickname'],
                gain=gain
            )
            total_gain = gain
            if (self.shop.get_user_items(group_id, user_id).get("淬火爪刀", 0) > 0 
                and abs(u_len - t_len) > 10 
                and u_len < t_len):
                extra_loot = int(target_data['length'] * 0.1)
                user_data['length'] += extra_loot
                total_gain += extra_loot
                text += f"\n🔥 淬火爪刀触发！额外掠夺 {extra_loot}cm！"
                self.shop.consume_item(group_id, user_id, "淬火爪刀")  

            if abs(u_len - t_len) >= 20 and user_data['hardness'] < target_data['hardness']:
                extra_gain = random.randint(3, 8)
                user_data['length'] += extra_gain
                total_gain += extra_gain
                text += f"\n🎁 由于极大劣势获胜，额外增加 {extra_gain}cm！"
            if abs(u_len - t_len) > 10 and u_len < t_len:
                stolen_length = int(target_data['length'] * 0.2)
                user_data['length'] += stolen_length
                total_gain += stolen_length
                target_data['length'] = max(1, target_data['length'] - stolen_length)
                text += f"\n🎉 {nickname} 掠夺了 {stolen_length}cm！"
            if abs(u_len - t_len) <= 5 and user_data['hardness'] > target_data['hardness']:
                text += f"\n🎉 {nickname} 因硬度优势获胜！"
            if total_gain == 0:
                text += f"\n{self.niuniu_texts['compare']['user_no_increase'].format(nickname=nickname)}"
        else:
            gain = random.randint(0, 6)
            loss = random.randint(1, 3)
            target_data['length'] += gain
            if self.shop.consume_item(group_id, user_id, "余震"):
                result_msg = [f"🛡️ 【余震生效】{nickname} 未减少长度！"]
            else:
                user_data['length'] = max(1, user_data['length'] - loss)
                result_msg = [f"💔 {nickname} 减少 {loss}cm"]
            text = random.choice(self.niuniu_texts['compare']['lose']).format(
                nickname=nickname,
                target_nickname=target_data['nickname'],
                loss=loss
            )
        # 硬度衰减
        if random.random() < 0.3:
            user_data['hardness'] = max(1, user_data['hardness'] - 1)
        if random.random() < 0.3:
            target_data['hardness'] = max(1, target_data['hardness'] - 1)

        self._save_niuniu_lengths()
        result_msg = [
            "⚔️ 【牛牛对决结果】 ⚔️",
            f"🗡️ {nickname}: {self.format_length(old_u_len)} → {self.format_length(user_data['length'])}",
            f"🛡️ {target_data['nickname']}: {self.format_length(old_t_len)} → {self.format_length(target_data['length'])}",
            f"📢 {text}"
        ]
        special_event_triggered = False
        if abs(u_len - t_len) <= 5 and random.random() < 0.075:
            result_msg.append("💥 双方势均力敌！")
            special_event_triggered = True
        # 硬度过低触发缠绕
        if not special_event_triggered and (user_data['hardness'] <= 2 or target_data['hardness'] <= 2) and random.random() < 0.05:
            # 记录双方原始长度
            original_user_len = user_data['length']
            original_target_len = target_data['length']
            
            # 执行减半操作
            user_data['length'] = max(1, original_user_len // 2)
            target_data['length'] = max(1, original_target_len // 2)
            
            # 检查发起方妙脆角
            if self.shop.get_user_items(group_id, user_id).get("妙脆角", 0) > 0:
                user_data['length'] = original_user_len  # 恢复发起方
                result_msg.append(f"🛡️ {nickname} 的妙脆角生效，防止了长度减半！")
                self.shop.consume_item(group_id, user_id, "妙脆角")
            
            # 检查目标方妙脆角
            if self.shop.get_user_items(group_id, target_id).get("妙脆角", 0) > 0:
                target_data['length'] = original_target_len  # 恢复目标方
                result_msg.append(f"🛡️ {target_data['nickname']} 的妙脆角生效，防止了长度减半！")
                self.shop.consume_item(group_id, target_id, "妙脆角")
            
            result_msg.append("双方牛牛因过于柔软发生缠绕！")
            special_event_triggered = True

        # 长度相近触发减半
        if not special_event_triggered and abs(u_len - t_len) < 10 and random.random() < 0.025:
            original_user_len = user_data['length']
            original_target_len = target_data['length']
            
            user_data['length'] = max(1, original_user_len // 2)
            target_data['length'] = max(1, original_target_len // 2)
            
            # 检查发起方
            if self.shop.get_user_items(group_id, user_id).get("妙脆角", 0) > 0:
                user_data['length'] = original_user_len
                result_msg.append(f"🛡️ {nickname} 的妙脆角生效，防止了长度减半！")
                self.shop.consume_item(group_id, user_id, "妙脆角")
            
            # 检查目标方
            if self.shop.get_user_items(group_id, target_id).get("妙脆角", 0) > 0:
                target_data['length'] = original_target_len
                result_msg.append(f"🛡️ {target_data['nickname']} 的妙脆角生效，防止了长度减半！")
                self.shop.consume_item(group_id, target_id, "妙脆角")
            
            result_msg.append(self.niuniu_texts['compare']['double_loss'].format(nickname1=nickname, nickname2=target_data['nickname']))
            special_event_triggered = True

        self._save_niuniu_lengths()
        yield event.plain_result("\n".join(result_msg))
    async def _show_status(self, event):
        """查看牛牛状态"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()

        group_data = self._load_niuniu_lengths().get(group_id, {'plugin_enabled': False})
        if not group_data.get('plugin_enabled', False):
            yield event.plain_result("❌ 插件未启用")
            return

        user_data = group_data.get(user_id)
        if not user_data:
            yield event.plain_result(self.niuniu_texts['my_niuniu']['not_registered'].format(nickname=nickname))
            return

        # 评价系统
        length = user_data['length']
        length_str = self.format_length(length)
        if length < 12:
            evaluation = random.choice(self.niuniu_texts['my_niuniu']['evaluation']['short'])
        elif length < 25:
            evaluation = random.choice(self.niuniu_texts['my_niuniu']['evaluation']['medium'])
        elif length < 50:
            evaluation = random.choice(self.niuniu_texts['my_niuniu']['evaluation']['long'])
        elif length < 100:
            evaluation = random.choice(self.niuniu_texts['my_niuniu']['evaluation']['very_long'])
        elif length < 200:
            evaluation = random.choice(self.niuniu_texts['my_niuniu']['evaluation']['super_long'])
        else:
            evaluation = random.choice(self.niuniu_texts['my_niuniu']['evaluation']['ultra_long'])

        text = self.niuniu_texts['my_niuniu']['info'].format(
            nickname=nickname,
            length=length_str,
            evaluation=evaluation
        )
        yield event.plain_result(text)

    async def _show_ranking(self, event):
        """显示排行榜"""
        group_id = str(event.message_obj.group_id)
        group_data = self._load_niuniu_lengths().get(group_id, {'plugin_enabled': False})
        if not group_data.get('plugin_enabled', False):
            yield event.plain_result("❌ 插件未启用")
            return

        # 过滤有效用户数据
        valid_users = [
            (uid, data) for uid, data in group_data.items()
            if isinstance(data, dict) and 'length' in data
        ]

        if not valid_users:
            yield event.plain_result(self.niuniu_texts['ranking']['no_data'])
            return

        # 排序并取前10
        sorted_users = sorted(valid_users, key=lambda x: x[1]['length'], reverse=True)[:10]

        # 构建排行榜
        ranking = [self.niuniu_texts['ranking']['header']]
        for idx, (uid, data) in enumerate(sorted_users, 1):
            ranking.append(
                self.niuniu_texts['ranking']['item'].format(
                    rank=idx,
                    name=data['nickname'],
                    length=self.format_length(data['length'])
                )
            )

        yield event.plain_result("\n".join(ranking))
    async def _show_menu(self, event):
        """显示菜单"""
        yield event.plain_result(self.niuniu_texts['menu']['default'])
    # endregion
