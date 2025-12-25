"""
配置文件选择器模块
负责发现、展示和选择表配置文件
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional


class ConfigSelector:
    """配置文件选择器"""
    
    def __init__(self, configs_dir: str = "config/table_configs"):
        """初始化配置选择器
        
        Args:
            configs_dir: 表配置文件目录
        """
        self.configs_dir = Path(configs_dir)
        self.configs = []
        self.current_index = 0
    
    def discover_configs(self) -> List[Dict[str, str]]:
        """发现所有表配置文件
        
        Returns:
            List[Dict]: 配置文件列表
            [{
                'filename': 'prod.json',
                'name': '生产环境全量同步',
                'description': '...',
                'path': Path('config/table_configs/prod.json')
            }]
        """
        configs = []
        
        # 检查配置目录是否存在
        if not self.configs_dir.exists():
            print(f"配置目录不存在: {self.configs_dir}")
            return configs
        
        # 查找所有.json文件
        json_files = list(self.configs_dir.glob("*.json"))
        
        for json_file in sorted(json_files):
            try:
                # 读取配置文件
                with open(json_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # 验证必需字段
                if 'name' not in config_data:
                    print(f"警告: 配置文件 {json_file.name} 缺少 'name' 字段，跳过")
                    continue
                
                if 'tables' not in config_data:
                    print(f"警告: 配置文件 {json_file.name} 缺少 'tables' 字段，跳过")
                    continue
                
                # 添加到配置列表
                configs.append({
                    'filename': json_file.name,
                    'name': config_data['name'],
                    'description': config_data.get('description', ''),
                    'path': json_file
                })
                
            except json.JSONDecodeError as e:
                print(f"错误: 配置文件 {json_file.name} JSON格式错误，跳过")
                print(f"  错误详情: {e}")
            except Exception as e:
                print(f"错误: 读取配置文件 {json_file.name} 失败，跳过")
                print(f"  错误详情: {e}")
        
        self.configs = configs
        return configs
    
    def display_menu(self) -> None:
        """显示选择菜单"""
        # 清屏
        self._clear_screen()
        
        # 显示标题
        print("=" * 60)
        print("SQL Server 数据同步系统")
        print("=" * 60)
        print()
        
        if not self.configs:
            print("未找到任何表配置文件")
            print(f"请在 {self.configs_dir} 目录下创建配置文件")
            print()
            return
        
        print("发现以下表配置文件:")
        print()
        
        # 显示所有配置文件
        for i, config in enumerate(self.configs):
            if i == self.current_index:
                # 高亮显示当前选择
                print(f"  [●] {config['name']}")
                if config['description']:
                    print(f"      描述: {config['description']}")
                print(f"      文件: {config['filename']}")
            else:
                # 普通显示
                print(f"  [○] {config['name']}")
                if config['description']:
                    print(f"      描述: {config['description']}")
                print(f"      文件: {config['filename']}")
            print()
        
        print("请使用 ↑↓ 键选择配置文件，按 Enter 确认:")
    
    def handle_input(self) -> Optional[Dict[str, str]]:
        """处理用户输入
        
        Returns:
            Dict[str, str]: 选中的配置文件信息，如果退出则返回None
        """
        if not self.configs:
            return None
        
        try:
            import keyboard
            use_keyboard = True
        except ImportError:
            print("未安装keyboard库，使用数字选择模式")
            use_keyboard = False
        
        if use_keyboard:
            return self._handle_keyboard_input()
        else:
            return self._handle_numeric_input()
    
    def _handle_keyboard_input(self) -> Optional[Dict[str, str]]:
        """使用键盘库处理输入
        
        Returns:
            Dict[str, str]: 选中的配置文件信息，如果退出则返回None
        """
        try:
            import keyboard
        except ImportError:
            print("错误: 无法导入keyboard库")
            return None
        
        print("\n提示: 使用键盘上下键选择，按Enter确认，按Esc退出")
        
        while True:
            self.display_menu()
            
            # 等待按键
            key = keyboard.read_key(suppress=True)
            
            if key == 'up':
                self.current_index = (self.current_index - 1) % len(self.configs)
            elif key == 'down':
                self.current_index = (self.current_index + 1) % len(self.configs)
            elif key == 'enter':
                print(f"\n已选择: {self.configs[self.current_index]['name']}")
                return self.configs[self.current_index]
            elif key == 'esc' or (key == 'c' and keyboard.is_pressed('ctrl')):
                print("\n用户取消操作")
                return None
    
    def _handle_numeric_input(self) -> Optional[Dict[str, str]]:
        """使用数字选择模式
        
        Returns:
            Dict[str, str]: 选中的配置文件信息，如果退出则返回None
        """
        while True:
            print()
            for i, config in enumerate(self.configs):
                print(f"  {i+1}. {config['name']} ({config['filename']})")
            
            print()
            try:
                choice = input("请输入配置编号 (0退出): ").strip()
                
                if choice == '0':
                    print("用户取消操作")
                    return None
                
                index = int(choice) - 1
                
                if 0 <= index < len(self.configs):
                    print(f"\n已选择: {self.configs[index]['name']}")
                    return self.configs[index]
                else:
                    print("无效的编号，请重新输入")
                    
            except ValueError:
                print("请输入有效的数字")
            except KeyboardInterrupt:
                print("\n用户取消操作")
                return None
    
    def display_and_select(self, configs: List[Dict[str, str]] = None) -> Optional[Dict[str, str]]:
        """显示菜单并选择配置文件
        
        Args:
            configs: 配置文件列表，如果为None则使用discovered_configs()
            
        Returns:
            Dict[str, str]: 选中的配置文件信息，如果退出则返回None
        """
        if configs is not None:
            self.configs = configs
        
        # 如果只有一个配置文件，自动选择
        if len(self.configs) == 1:
            selected = self.configs[0]
            print(f"自动选择唯一配置: {selected['name']}")
            print(f"配置文件: {selected['filename']}")
            return selected
        
        # 如果有多个配置文件，显示选择菜单
        if len(self.configs) > 1:
            return self.handle_input()
        
        # 没有配置文件
        return None
    
    @staticmethod
    def _clear_screen():
        """清屏"""
        import os
        if os.name == 'nt':  # Windows
            os.system('cls')
        else:  # Linux/Mac
            os.system('clear')
