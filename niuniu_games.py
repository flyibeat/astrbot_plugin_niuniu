import random
import time
import yaml
from astrbot.api.all import AstrMessageEvent

class NiuniuGames:
    def __init__(self, main_plugin):
        self.main = main_plugin  # 主插件实例

    async def start_rush(self, event: AstrMessageEvent):
        """冲(咖啡)游戏"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()

        # 检查插件是否启用
        if not self.main.get_group_data(group_id).get('plugin_enabled', False):
            yield event.plain_result("❌ 插件未启用")
            return

        # 获取用户数据
        user_data = self.main.get_user_data(group_id, user_id)
        if not user_data:
            yield event.plain_result("❌ 请先注册牛牛")
            return

        # 检查冷却时间
        # last_rush_end_time = user_data.get('last_rush_end_time', 0)
        # current_time = time.time()
        # if current_time - last_rush_end_time < 1800:  # 30分钟冷却时间
        #     remaining_time = 1800 - (current_time - last_rush_end_time)
        #     mins = int(remaining_time // 60) + 1
        #     yield event.plain_result(f"⏳ {nickname} 牛牛冲累了，休息{mins}分钟再冲吧")
        #     return

        # 检查是否已经在冲
        if user_data.get('is_rushing', False):
            remaining_time = user_data['rush_start_time'] + 14400 - time.time()  # 4小时 = 14400秒
            if remaining_time > 0:
                mins = int(remaining_time // 60) + 1
                yield event.plain_result(f"⏳ {nickname} 你已经在冲了，预计还剩{mins}分钟达到上限")
                return
                
        # 检查开冲日期
        last_rush_start_time = user_data.get('rush_start_time', 0)
        today_start = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, 0))
        if today_start > last_rush_start_time:  #判断上次开冲是在昨天
            user_data['today_rush_count'] = 0
            today_rush_count = 0
            
        # 检查今日已冲次数
        today_rush_count = user_data.get('today_rush_count', 0)
        if today_rush_count > 6:
            yield event.plain_result(f" {nickname} 你冲得到处都是，明天再来吧")
            return



        # 开始
        user_data['is_rushing'] = True
        user_data['rush_start_time'] = time.time()
        user_data['today_rush_count'] = today_rush_count + 1
        self.main._save_niuniu_lengths()

        yield event.plain_result(f"💪 {nickname} 芜湖！开冲！输入\"停止开冲\"来结束并结算金币。")

    async def stop_rush(self, event: AstrMessageEvent):
        """停止开冲并结算金币"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()

        # 获取用户数据
        user_data = self.main.get_user_data(group_id, user_id)
        if not user_data:
            yield event.plain_result("❌ 请先注册牛牛")
            return

        # 检查是否在冲
        if not user_data.get('is_rushing', False):
            yield event.plain_result(f"❌ {nickname} 你当前没有在冲")
            return

        # 计算时间
        work_time = time.time() - user_data['rush_start_time']

        # 如果时间少于10分钟，没有奖励
        if work_time < 600:  # 10分钟 = 600秒
            yield event.plain_result(f"❌ {nickname} 至少冲够十分钟才能停")
            return

        # 如果时间超过4小时，按4小时计算
        work_time = min(work_time, 14400)  # 4小时 = 14400秒

        # 固定每分钟1个金币
        coins = int(work_time / 60)

        # 更新用户金币
        user_data['coins'] = user_data.get('coins', 0) + coins
        self.main._save_niuniu_lengths()

        yield event.plain_result(f"🎉 {nickname} 总算冲够了！你获得了 {coins} 金币！")

        # 重置状态
        user_data['is_rushing'] = False
        user_data['last_rush_end_time'] = time.time()  # 记录本次冲结束时间
        self.main._save_niuniu_lengths()

    async def fly_plane(self, event: AstrMessageEvent):
        """飞机游戏"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()

        # 检查插件是否启用
        if not self.main.get_group_data(group_id).get('plugin_enabled', False):
            yield event.plain_result("❌ 插件未启用")
            return

        # 获取用户数据
        user_data = self.main.get_user_data(group_id, user_id)
        if not user_data:
            yield event.plain_result("❌ 请先注册牛牛")
            return

        # 检查冷却时间
        last_fly_time = user_data.get('last_fly_time', 0)
        current_time = time.time()
        if current_time - last_fly_time < 14400:  # 4小时
            remaining_time = 14400 - (current_time - last_fly_time)
            mins = int(remaining_time // 60) + 1
            yield event.plain_result(f"✈️ 油箱空了，{nickname} {mins}分钟后可再起飞")
            return

        # 飞行事件
        fly_events = [
            {"description": "牛牛没赶上飞机，不过也算出来透了口气", "coins": random.randint(20, 40)},
            {"description": "竟然赶上了国际航班，遇到了兴奋的大母猴", "coins": random.randint(80, 100)},
            {"description": "无惊无险，牛牛顺利抵达目的地", "coins": random.randint(70,80)},
            {"description": "牛牛刚出来就遇到了冷空气，冻得像个鹌鹑似的", "coins": random.randint(40, 60)},
            {"description": "牛牛好像到奇怪的地方，不过也算是完成了目标", "coins": random.randint(60, 80)}
        ]

        # 随机选择一个事件
        event_data = random.choice(fly_events)
        description = event_data["description"]
        coins = event_data["coins"]

        # 更新用户金币
        user_data['coins'] = user_data.get('coins', 0) + coins
        user_data['last_fly_time'] = current_time
        self.main._save_niuniu_lengths()

        yield event.plain_result(f"🎉 {nickname} {description}！你获得了 {coins} 金币！")

    def update_user_coins(self, group_id: str, user_id: str, coins: float):
        """更新用户金币"""
        user_data = self.main.get_user_data(group_id, user_id)
        if user_data:
            user_data['coins'] = user_data.get('coins', 0) + coins
            self.main._save_niuniu_lengths()

    def get_user_coins(self, group_id: str, user_id: str) -> float:
        """获取用户金币"""
        user_data = self.main.get_user_data(group_id, user_id)
        return user_data.get('coins', 0) if user_data else 0
