"""
处理答案文件，将txt内容转换为表格形式
"""
import json
import re
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional


def parse_single_answer_file(file_path: Path) -> pd.DataFrame:
    """
    解析单个答案txt文件，转换为DataFrame表格
    
    Args:
        file_path: txt文件路径
        
    Returns:
        包含解析数据的DataFrame，带有file列记录来源文件名
    """
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    # 尝试提取JSON内容（处理可能包含```json标记的情况）
    json_content = extract_json_content(content)
    
    if not json_content:
        print(f"警告：文件 {file_path.name} 中未找到有效的JSON内容")
        return pd.DataFrame()
    
    try:
        # 解析JSON
        data = json.loads(json_content)
        
        # 提取magnetocaloric_data
        if 'magnetocaloric_data' in data:
            records = data['magnetocaloric_data']
        else:
            print(f"警告：文件 {file_path.name} 中未找到magnetocaloric_data字段")
            return pd.DataFrame()
        
        # 转换为DataFrame
        df = pd.DataFrame(records)
        
        # 添加file列记录来源文件名
        df['file'] = file_path.stem
        
        return df
        
    except json.JSONDecodeError as e:
        print(f"错误：文件 {file_path.name} JSON解析失败: {e}")
        return pd.DataFrame()


def extract_json_content(text: str) -> Optional[str]:
    """
    从文本中提取JSON内容，处理可能包含```json标记的情况
    
    Args:
        text: 原始文本内容
        
    Returns:
        提取的JSON字符串，如果未找到则返回None
    """
    # 情况1：检查是否有```json标记
    json_pattern = r'```json\s*(.*?)\s*```'
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # 情况2：检查是否直接是JSON格式（以{开始，以}结束）
    text = text.strip()
    if text.startswith('{') and text.endswith('}'):
        return text
    
    # 情况3：尝试提取花括号内的内容
    brace_pattern = r'\{.*\}'
    match = re.search(brace_pattern, text, re.DOTALL)
    if match:
        return match.group(0).strip()
    
    return None


def process_all_answer_files(folder_path: Path, output_csv_path: Path) -> pd.DataFrame:
    """
    处理文件夹下所有的答案txt文件，汇总为总表
    
    Args:
        folder_path: 答案文件夹路径
        output_csv_path: 输出CSV文件路径
        
    Returns:
        汇总后的DataFrame
    """
    if not folder_path.exists():
        print(f"错误：文件夹 {folder_path} 不存在")
        return pd.DataFrame()
    
    # 获取所有txt文件
    txt_files = list(folder_path.glob("*.txt"))
    if not txt_files:
        print(f"警告：文件夹 {folder_path} 中没有找到txt文件")
        return pd.DataFrame()
    
    print(f"找到 {len(txt_files)} 个txt文件")
    
    # 处理每个文件并收集结果
    all_dataframes = []
    
    for txt_file in txt_files:
        # print(f"正在处理: {txt_file.name}")
        df = parse_single_answer_file(txt_file)
        if not df.empty:
            all_dataframes.append(df)
    
    if not all_dataframes:
        print("错误：没有成功解析任何文件")
        return pd.DataFrame()
    
    # 合并所有DataFrame
    result_df = pd.concat(all_dataframes, ignore_index=True)
    
    # 保存为CSV
    result_df.to_csv(output_csv_path, index=False, encoding='utf-8-sig')
    print(f"结果已保存到: {output_csv_path}")
    print(f"总共处理了 {len(result_df)} 条记录")
    
    return result_df


if __name__ == "__main__":
    # 测试代码
    data_folder = Path("../../../data/磁热材料/answer")
    output_csv = data_folder / "汇总结果.csv"
    
    # 处理所有文件
    result = process_all_answer_files(data_folder, output_csv)
    
    if not result.empty:
        print("\n汇总结果预览:")
        print(result.head())
        print(f"\n列名: {list(result.columns)}")
        print(f"数据形状: {result.shape}")