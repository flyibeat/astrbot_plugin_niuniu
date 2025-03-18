import os
import yaml
from typing import Dict, Any
from astrbot.api.all import Context, AstrMessageEvent

class NiuniuShop:
    def __init__(self, main_plugin):
        self.main = main_plugin  # 主插件实例
        self.shop_config_path = os.path.join('data', 'plugins', 'astrbot_plugin_niuniu', 'niuniu_shop.yml')
        self.shop_items = self._load_shop_config()

    def _load_shop_config(self) -> list:
        """加载商城配置"""
        default_config = [
            {
                'id': 1,
                'name': "巴黎世家",
                'type': 'active',
                'desc': "💎 立即增加3点硬度",
                'effect': {'hardness': 3},
                'price': 50  
            },
            {
                'id': 2,
                'name': "巴适得板生长素",
                'type': 'active',
                'desc': "立即增加20cm长度，但会减少2点硬度",
                'effect': {'length': 20, 'hardness': -2},
                'price': 50 
            },
            {
                'id': 3,
                'name': "妙脆角",
                'type': 'passive', 
                'max': 3, 
                'desc': "防止一次长度减半",
                'effect': 'prevent_halving', 
                'price': 70 
            },
            {
                'id': 4,
                'name': "淬火爪刀",
                'type': 'passive',
                'max': 2, 
                'desc': "触发掠夺时，额外掠夺10%长度",
                'effect': 'bonus_loot',
                'price': 70
            },
            {
                'id': 5,
                'name': "余震",
                'type': 'passive',
                'max': 3,
                'desc': "主动比划时，如果失败，百分百不扣长度",
                'effect': 'no_deduct_on_fail',
                'price': 30  
            },
            {
                'id': 6,
                'name': "不灭之握",
                'type': 'active',
                'desc': "直接增加30cm长度",
                'effect': {'length': 30},
                'price': 100  
            },
            {
                'id': 7,
                'name': "致命节奏",  
                'type': 'passive',  
                'max': 20,  
                'quantity': 5,  
                'desc': "短时间内多次打胶或比划，同时不受30分钟内连续打胶的debuff",
                'effect': 'no_30min_debuff', 
                'price': 100 
            },
            {
                'id': 8,
                'name': "阿姆斯特朗旋风喷射炮",
                'type': 'active',
                'desc': "长度直接+1m，硬度+10",
                'effect': {'length': 100, 'hardness': 10},
                'price': 500  
            },
            {
                'id': 9,
                'name': "夺心魔蝌蚪罐头",
                'type': 'passive',
                'max': 1,
                'desc': "在比划时，有50%的概率夺取对方全部长度，10%的概率清空自己的长度，40%的概率无效",
                'effect': 'steal_or_clear',
                'price': 600
            }
        ]
        
        try:
            if os.path.exists(self.shop_config_path):
                with open(self.shop_config_path, 'r', encoding='utf-8') as f:
                    custom_config = yaml.safe_load(f) or []
                    # 配置合并逻辑
                    return self._merge_config(default_config, custom_config)
            return default_config
        except Exception as e:
            return default_config

    def _merge_config(self, base: list, custom: list) -> list:
        """合并默认配置和自定义配置"""
        config_map = {item['id']: item for item in base}
        for custom_item in custom:
            if custom_item['id'] in config_map:
                config_map[custom_item['id']].update(custom_item)
            else:
                config_map[custom_item['id']] = custom_item
        return list(config_map.values())

    async def show_shop(self, event: AstrMessageEvent):
        """显示商城"""
        shop_list = ["🛒 牛牛商城（使用 牛牛购买+编号）"]
        for item in self.shop_items:
            shop_list.append(f"{item['id']}. {item['name']} - {item['desc']} (价格: {item['price']} 金币)")
        yield event.plain_result("\n".join(shop_list))

    async def handle_buy(self, event: AstrMessageEvent):    
        """处理购买命令"""
        msg_parts = event.message_str.split()
        if len(msg_parts) < 2 or not msg_parts[1].isdigit():
            yield event.plain_result("❌ 格式：牛牛购买 商品编号\n例：牛牛购买 1")
            return

        item_id = int(msg_parts[1])
        selected_item = next((i for i in self.shop_items if i['id'] == item_id), None)
        
        if not selected_item:
            yield event.plain_result("❌ 无效的商品编号")
            return

        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())

        # 获取用户金币
        user_coins = self.get_user_coins(group_id, user_id)

        # 检查用户是否有足够的金币
        if user_coins < selected_item['price']:
            yield event.plain_result("❌ 金币不足，无法购买")
            return

        try:
            result_msg = []
            if selected_item['type'] == 'passive':
                user_data = self._get_user_data(group_id, user_id)
                user_data.setdefault('items', {})
                current = user_data['items'].get(selected_item['name'], 0)
                if current >= selected_item.get('max', 3):
                    yield event.plain_result(f"⚠️ 已达到最大持有量（最大{selected_item['max']}个）")
                    return
                user_data['items'][selected_item['name']] = current + 1
                result_msg.append(f"📦 获得 {selected_item['name']}x1")
                self._save_user_data(group_id, user_id, user_data)
            elif selected_item['type'] == 'active':
                user_data = self._get_user_data(group_id, user_id)
                if isinstance(selected_item['effect'], dict):
                    for effect_key, effect_value in selected_item['effect'].items():
                        original = user_data.get(effect_key, 1 if effect_key == 'hardness' else 10)
                        user_data[effect_key] = original + effect_value
                        if effect_value >= 0:
                            result_msg.append(f"✨ {effect_key}增加了{effect_value}")
                        else:
                            result_msg.append(f"✨ {effect_key}减少了{-effect_value}")
                else:
                    effect_key = selected_item['effect']
                    effect_value = 1  # 默认值，可以根据实际需求调整
                    original = user_data.get(effect_key, 1 if effect_key == 'hardness' else 10)
                    user_data[effect_key] = original + effect_value
                    result_msg.append(f"✨ {effect_key}增加了{effect_value}")
                self._save_user_data(group_id, user_id, user_data)

            # 扣除金币
            self.update_user_coins(group_id, user_id, user_coins - selected_item['price'])

            yield event.plain_result("✅ 购买成功\n" + "\n".join(result_msg))
        
        except Exception as e:
            self.main.context.logger.error(f"购买错误: {str(e)}")
            yield event.plain_result("⚠️ 购买过程中出现错误，请稍后再试")

    def get_sign_coins(self, group_id: str, user_id: str) -> float:
        """获取签到插件的金币"""
        sign_data_path = os.path.join('data', 'sign_data.yml')
        if not os.path.exists(sign_data_path):
            return 0.0

        with open(sign_data_path, 'r', encoding='utf-8') as f:
            sign_data = yaml.safe_load(f) or {}

        return sign_data.get(group_id, {}).get(user_id, {}).get('coins', 0.0)

    def update_sign_coins(self, group_id: str, user_id: str, coins: float):
        """更新签到插件的金币"""
        sign_data_path = os.path.join('data', 'sign_data.yml')
        if not os.path.exists(sign_data_path):
            with open(sign_data_path, 'w', encoding='utf-8') as f:
                yaml.dump({}, f)

        with open(sign_data_path, 'r', encoding='utf-8') as f:
            sign_data = yaml.safe_load(f) or {}

        user_data = sign_data.setdefault(group_id, {}).setdefault(user_id, {})
        user_data['coins'] = coins

        with open(sign_data_path, 'w', encoding='utf-8') as f:
            yaml.dump(sign_data, f, allow_unicode=True)

    def get_user_coins(self, group_id: str, user_id: str) -> float:
        """获取总金币"""
        sign_coins = self.get_sign_coins(group_id, user_id)
        new_game_coins = self._get_new_game_coins(group_id, user_id)
        return sign_coins + new_game_coins

    def _get_new_game_coins(self, group_id: str, user_id: str) -> float:
        """获取牛牛游戏的金币"""
        user_data_path = os.path.join('data', 'niuniu_lengths.yml')
        if not os.path.exists(user_data_path):
            return 0.0

        with open(user_data_path, 'r', encoding='utf-8') as f:
            user_data = yaml.safe_load(f) or {}

        return user_data.get(group_id, {}).get(user_id, {}).get('coins', 0.0)

    async def handle_buy(self, event: AstrMessageEvent):
        """处理购买命令"""
        msg_parts = event.message_str.split()
        if len(msg_parts) < 2 or not msg_parts[1].isdigit():
            yield event.plain_result("❌ 格式：牛牛购买 商品编号\n例：牛牛购买 1")
            return

        item_id = int(msg_parts[1])
        selected_item = next((i for i in self.shop_items if i['id'] == item_id), None)
        
        if not selected_item:
            yield event.plain_result("❌ 无效的商品编号")
            return

        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())

        # 获取用户金币
        user_coins = self.get_user_coins(group_id, user_id)

        # 检查用户是否有足够的金币
        if user_coins < selected_item['price']:
            yield event.plain_result("❌ 金币不足，无法购买")
            return

        try:
            result_msg = []
            if selected_item['type'] == 'passive':
                user_data = self._get_user_data(group_id, user_id)
                user_data.setdefault('items', {})
                current = user_data['items'].get(selected_item['name'], 0)
                if current >= selected_item.get('max', 3):
                    yield event.plain_result(f"⚠️ 已达到最大持有量（最大{selected_item['max']}个）")
                    return
                user_data['items'][selected_item['name']] = current + 1
                result_msg.append(f"📦 获得 {selected_item['name']}x1")
                self._save_user_data(group_id, user_id, user_data)
            elif selected_item['type'] == 'active':
                user_data = self._get_user_data(group_id, user_id)
                if isinstance(selected_item['effect'], dict):
                    for effect_key, effect_value in selected_item['effect'].items():
                        original = user_data.get(effect_key, 1 if effect_key == 'hardness' else 10)
                        user_data[effect_key] = original + effect_value
                        if effect_value >= 0:
                            result_msg.append(f"✨ {effect_key}增加了{effect_value}")
                        else:
                            result_msg.append(f"✨ {effect_key}减少了{-effect_value}")
                else:
                    effect_key = selected_item['effect']
                    effect_value = 1  # 默认值，可以根据实际需求调整
                    original = user_data.get(effect_key, 1 if effect_key == 'hardness' else 10)
                    user_data[effect_key] = original + effect_value
                    result_msg.append(f"✨ {effect_key}增加了{effect_value}")
                self._save_user_data(group_id, user_id, user_data)

            # 扣除金币
            self.update_user_coins(group_id, user_id, user_coins - selected_item['price'])

            yield event.plain_result("✅ 购买成功\n" + "\n".join(result_msg))
        
        except Exception as e:
            print(f"购买错误: {str(e)}")
            yield event.plain_result("⚠️ 购买过程中出现错误，请稍后再试")

    def _update_new_game_coins(self, group_id: str, user_id: str, coins: float):
        """更新牛牛游戏的金币"""
        user_data_path = os.path.join('data', 'niuniu_lengths.yml')
        if not os.path.exists(user_data_path):
            with open(user_data_path, 'w', encoding='utf-8') as f:
                yaml.dump({}, f)

        with open(user_data_path, 'r', encoding='utf-8') as f:
            user_data = yaml.safe_load(f) or {}

        group_data = user_data.setdefault(group_id, {})
        user_info = group_data.setdefault(user_id, {})
        user_info['coins'] = coins

        with open(user_data_path, 'w', encoding='utf-8') as f:
            yaml.dump(user_data, f, allow_unicode=True)


    def update_user_coins(self, group_id: str, user_id: str, coins: float):
        """更新总金币"""
        current_coins = self.get_user_coins(group_id, user_id)
        new_game_coins = self._get_new_game_coins(group_id, user_id)
        sign_coins = self.get_sign_coins(group_id, user_id)

        if new_game_coins >= current_coins - coins:
            self._update_new_game_coins(group_id, user_id, new_game_coins - (current_coins - coins))
        else:
            remaining = (current_coins - coins) - new_game_coins
            self._update_new_game_coins(group_id, user_id, 0)
            self.update_sign_coins(group_id, user_id, sign_coins - remaining)

    def _get_user_data(self, group_id: str, user_id: str) -> Dict[str, Any]:
        """获取用户数据"""
        user_data_path = os.path.join('data', 'niuniu_lengths.yml')
        if not os.path.exists(user_data_path):
            return {}

        with open(user_data_path, 'r', encoding='utf-8') as f:
            user_data = yaml.safe_load(f) or {}

        group_data = user_data.get(group_id, {})
        user_info = group_data.get(user_id, {})
        return user_info

    def _save_user_data(self, group_id: str, user_id: str, user_data: Dict[str, Any]):
        """保存用户数据"""
        user_data_path = os.path.join('data', 'niuniu_lengths.yml')
        if not os.path.exists(user_data_path):
            with open(user_data_path, 'w', encoding='utf-8') as f:
                yaml.dump({}, f)

        with open(user_data_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        group_data = data.setdefault(group_id, {})
        group_data[user_id] = user_data

        with open(user_data_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True)

    def get_user_items(self, group_id: str, user_id: str) -> Dict[str, int]:
        """获取用户道具"""
        user_data = self._get_user_data(group_id, user_id)
        return user_data.get('items', {})

    def consume_item(self, group_id: str, user_id: str, item_name: str) -> bool:
        """消耗道具返回是否成功"""
        user_data = self._get_user_data(group_id, user_id)
        items = user_data.get('items', {})

        if items.get(item_name, 0) > 0:
            items[item_name] -= 1
            if items[item_name] == 0:
                del items[item_name]
            user_data['items'] = items
            self._save_user_data(group_id, user_id, user_data)
            return True
        return False

    async def show_items(self, event: AstrMessageEvent):
        """显示用户道具及金币总额"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        items = self.get_user_items(group_id, user_id)
        
        result_list = ["📦 你的道具背包："]

        # 显示道具信息
        if items:
            for name, count in items.items():
                # 使用 next() 函数时提供默认值 None
                item_info = next((i for i in self.shop_items if i['name'] == name), None)
                if item_info:
                    result_list.append(f"🔹 {name}x{count} - {item_info['desc']}")

        else:
            result_list.append("🛍️ 你的背包里还没有道具哦~")
        
        # 显示金币总额
        total_coins = self.get_user_coins(group_id, user_id)
        result_list.append(f"💰 你的金币：{total_coins}")

        yield event.plain_result("\n".join(result_list))
