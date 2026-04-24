import re
import json
import pandas as pd
from copy import deepcopy

def extract_content(file_path, excluded_titles=None, encode='utf-8'):
    try:
        with open(file_path, 'r', encoding=encode) as file:
            content = file.read()
    except Exception as e:
        error_type = type(e).__name__
        return f'错误：不能打开文件{file_path}（{error_type}: {str(e)}）'

    if excluded_titles is None:
        excluded_titles = [
            "ACKNOWLEDGMENT", "ACKNOWLEDGMENTS",
            "ACKNOWLEDGEMENT", "ACKNOWLEDGEMENTS",
            "REFERENCES", "Supplementary material",
            "Contributors", "参考文献"
        ]

    # 编译一个正则列表，支持匹配含空格的标题，例如 R E F E R E N C E S
    excluded_title_patterns = [
        # re.compile(r'^' + r'\s*'.join(list(title)) + r'\s*$', flags=re.IGNORECASE) # 只有相关内容
        re.compile(r'.*' + r'\s*'.join(list(title)) + r'.*', flags=re.IGNORECASE) # 包含相关内容就算
        for title in excluded_titles
    ]

    def is_excluded_title(title):
        normalized = title.strip().upper().replace(" ", "")
        for pattern in excluded_title_patterns:
            if pattern.match(' '.join(list(normalized))):
                return True
        return False

    # 用正则表达式匹配标题和其后的内容
    blocks = re.split(r'(^# .+)', content, flags=re.M)
    blocks = [block.strip() for block in blocks if block.strip()]

    cleaned_content = ""
    i = 0
    while i < len(blocks):
        block = blocks[i]
        if block.startswith("# "):  # 是标题
            title = block[2:].strip()  # 去掉 "# "
            if is_excluded_title(title):
                i += 2  # 跳过标题 + 其后的正文块
                continue
            else:
                cleaned_content += block + "\n"
                if i + 1 < len(blocks):
                    cleaned_content += blocks[i + 1] + "\n"
                i += 2
        else:
            # 非标题块（如前置内容）
            cleaned_content += block + "\n"
            i += 1

    return cleaned_content.strip()

def split_markdown(file_path, excluded_titles=None, encode='utf-8'):
    try:
        with open(file_path, 'r', encoding=encode) as file:
            content = file.read()
    except Exception as e:
        error_type = type(e).__name__
        return {'错误': f'不能打开文件{file_path}（{error_type}: {str(e)}）'}

    if excluded_titles is None:
        excluded_titles = [
            "ACKNOWLEDGMENT", "ACKNOWLEDGMENTS",
            "ACKNOWLEDGEMENT", "ACKNOWLEDGEMENTS",
            "REFERENCES", "Supplementary material",
            "参考文献", "Data availability"
        ]

    # 编译一个正则列表，支持匹配含空格的标题，例如 R E F E R E N C E S
    excluded_title_patterns = [
        # re.compile(r'^' + r'\s*'.join(list(title)) + r'\s*$', flags=re.IGNORECASE) # 只有相关内容
        re.compile(r'.*' + r'\s*'.join(list(title)) + r'.*', flags=re.IGNORECASE) # 包含相关内容就算
        for title in excluded_titles
    ]

    def is_excluded_title(title):
        normalized = title.strip().upper().replace(" ", "")
        for pattern in excluded_title_patterns:
            if pattern.match(' '.join(list(normalized))):
                return True
        return False

    # 用正则表达式匹配标题和其后的内容
    blocks = re.split(r'(^# .+)', content, flags=re.M)
    blocks = [block.strip() for block in blocks if block.strip()]

    result = {}
    current_title = None
    current_content = []
    title_part_num = {}
    skip_current_section = False

    def split_paragraphs(text):
        """按段落拆分，如果段落过长则再按句子拆分，同时处理 $$公式$$ 与前后段落的合并"""
        import re

        # 按 \n\n 拆分段落
        chunks = text.split('\n\n')

        # 处理公式块 $$...$$
        merged_chunks = []
        i = 0
        while i < len(chunks):
            chunk = chunks[i]

            if chunk.startswith('$$') and chunk.endswith('$$'):
                # 检查前一个段落是否以标点符号结尾
                if merged_chunks and not re.search(r'[。！？.!?]$', merged_chunks[-1].strip()):
                    merged_chunks[-1] += '\n\n' + chunk
                else:
                    merged_chunks.append(chunk)

                # 检查后一个段落首字母是否为小写，如果是则合并
                if i + 1 < len(chunks) and re.match(r'^[a-z]', chunks[i + 1].strip()):
                    merged_chunks[-1] += '\n\n' + chunks[i + 1]
                    i += 1  # 跳过已经合并的下一个段落
            else:
                merged_chunks.append(chunk)
            i += 1

        return merged_chunks

    for block in blocks:
        if block.startswith('# '):  # 是标题
            # 在切换新标题之前，处理前一个标题内容（如果不跳过）
            if current_title and not skip_current_section:
                full_content = '\n'.join(current_content)
                part_num = title_part_num.get(current_title, 1)
                for chunk in split_paragraphs(full_content):
                    result[f'{current_title}_part{part_num}'] = chunk
                    part_num += 1
                title_part_num[current_title] = part_num

            current_title_text = block[2:].strip()
            current_title = current_title_text
            current_content = []
            skip_current_section = is_excluded_title(current_title_text)
        else:
            if not skip_current_section:
                current_content.append(block)

    # 最后一个标题块的处理
    if current_title and not skip_current_section:
        full_content = '\n'.join(current_content)
        part_num = title_part_num.get(current_title, 1)
        for chunk in split_paragraphs(full_content):
            result[f'{current_title}_part{part_num}'] = chunk
            part_num += 1

    return result


def split_large_texts(data, length_threshold=5000, overlap=500):
    """
    对字典中的文本进行长度截断并分段，超过 length_threshold 的文本进行分段。

    参数：
    - data: dict, 原始数据，格式 {位置: 内容}
    - length_threshold: int, 单段最大长度
    - overlap: int, 分段之间的重叠长度

    返回：
    - new_data: dict, 分段后的数据，超过长度的文本被切分并重新标记
    """
    new_data = {}

    for key, text in data.items():
        text_len = len(text)
        if text_len <= length_threshold:
            # 不需要切分的直接加入
            new_data[key] = text
        else:
            # 需要切分
            start = 0
            i = 0
            while start < text_len:
                end = start + length_threshold
                segment = text[start:end]
                new_key = f"{key}_{i}"
                new_data[new_key] = segment
                i += 1
                start += length_threshold - overlap  # 下一段开始位置，考虑重叠

    return new_data


def expand_json(base_json, dict_map, key_value_names):
    """
    base_json: dict，原始json
    dict_map: dict，要展开的字典
    key_value_names: list，长度为2，[key_name, value_name]

    return: list，与dict_map长度相同，每个元素为扩展后的json
    """
    results = []
    key_name, value_name = key_value_names

    for k, v in dict_map.items():
        new_json = deepcopy(base_json)  # 保留原json
        new_json[key_name] = k
        new_json[value_name] = v
        results.append(new_json)

    return results


def save_as_markdown(expanded, md_file, keys_to_include=None):
    """
    expanded: list[dict]   expand_json生成的结果
    md_file: str           保存的md文件路径
    keys_to_include: list[str] 或 None
        - None: 生成所有键值对
        - list[str]: 只生成指定键

    Markdown格式：
    [key1]
    value1
    [key2]
    value2
    ...
    """
    with open(md_file, "w", encoding="utf-8") as f:
        for idx, item in enumerate(expanded, 1):
            # f.write(f"### JSON {idx}\n\n")  # 每条JSON序号
            if keys_to_include is None:
                # 全部键值对
                for k, v in item.items():
                    f.write(f"[{k}]\n{v}\n\n")
            else:
                # 只生成指定键
                for k in keys_to_include:
                    if k in item:
                        f.write(f"[{k}]\n{item[k]}\n\n")
            f.write("\n---\n\n")

def shift_md_headings(md_text: str, base_level: int = 2) -> str:
    """将markdown文本中的标题级数整体后移，比如 # -> ### （base_level=2 -> +1）"""

    def replace_heading(match):
        hashes = match.group(1)
        heading_text = match.group(2)
        new_hashes = '#' * (len(hashes) + base_level)
        return f"{new_hashes} {heading_text}"

    return re.sub(r'^(#{1,6})\s+(.*)', replace_heading, md_text, flags=re.MULTILINE)

def df_to_markdown(df: pd.DataFrame, primary_column: str, secondary_columns: list, link_dict: dict = None) -> str:
    lines = []
    link_dict = link_dict or {}

    for idx, row in df.iterrows():
        # 一级标题处理
        title_text = f"{primary_column}：{row[primary_column]}"
        if primary_column in link_dict:
            url = str(row[link_dict[primary_column]])
            primary_title = f"# [{title_text}]({url})"
        else:
            primary_title = f"# {title_text}"
        lines.append(primary_title)
        lines.append("")

        # 二级及以下内容处理
        for col in secondary_columns:
            # 二级标题（可能加链接）
            if col in link_dict:
                url = str(row[link_dict[col]])
                secondary_title = f"## [{col}]({url})"
            else:
                secondary_title = f"## {col}"
            lines.append(secondary_title)

            # 内容
            content = str(row[col]) if pd.notna(row[col]) else ""
            # 判断内容是否可能是 Markdown
            if re.search(r'(^|\n)#{1,6} ', content):
                # 需要偏移标题级数（当前是二级标题，所以base_level=2）
                content = shift_md_headings(content, base_level=2)
            lines.append(content)
            lines.append("")

        # 添加分隔线
        lines.append("---")
        lines.append("")

    return '\n'.join(lines)

if __name__ == '__main__':
    # ************ extract_content 试用 ************** 开始
    # file_path = 'Franco 等 - 2018 - Magnetocaloric effect From materials research to refrigeration devices'
    # file_path = file_path + '/auto/' + file_path + '.md'
    # a = extract_content(file_path)
    # with open('13.md', 'w', encoding='utf-8') as file:
    #     file.write(a)
    # ************ extract_content 试用 ************** 结束

    # ************ split_markdown 试用 ************** 开始
    # file_path = 'Franco 等 - 2018 - Magnetocaloric effect From materials research to refrigeration devices'
    # file_path = file_path + '/auto/' + file_path + '.md'
    file_path = '原文.md'
    a = split_markdown(file_path)
    a = split_large_texts(a)

    base_json = {"Article DOI": '10.1016/j.pmatsci.2017.10.005', "Article Title": "Magnetocaloric effect: From materials research to refrigeration devices"}
    key_value_names = ["Content position", "Content"]
    expanded = expand_json(base_json, dict_map=a, key_value_names=key_value_names)
    with open("expanded.json", "w", encoding="utf-8") as f:
        json.dump(expanded, f, indent=4, ensure_ascii=False)

    save_as_markdown(expanded, "expanded.md")
    # save_as_markdown(expanded, "expanded.md", keys_to_include=["Content position", "Content"])
    # ************ split_markdown 试用 ************** 结束

    # ************ 调用AI添加信息 ************** 开始
    # from 通用型AI助手_v1 import AI_Assistant
    #
    # chat = AI_Assistant()
    # chat.url_generate = url = "http://127.0.0.1:1234/v1/chat/completions"
    # chat.model_generate = "qwen/qwen3-32b"
    #
    # prm = '''
    # 我要基于科研文章生成自己的数据库用于RAG建设，下面我会给你一些文字信息，需要你帮我判断是否为有用信息。
    # 有用信息为：具有逻辑顺序的语句或段落。
    # 无用信息：
    # 1.人名的罗列，如：V. Franco ⇑, J.S. Blázquez, J.J. Ipus, J.Y. Law, L.M. Moreno-Ramírez, A. Conde
    # 2.工作单位的罗列，如：Dpto. Física de la Materia Condensada, ICMSE-CSIC, Universidad de Sevilla, P.O. Box 1065, 41080 Sevilla, Spain
    # 3.其他词语的简单罗列，而没有相关逻辑，如目录、注册信息等格式。
    # 4.乱码等不具有有用信息的字符串。
    # 5.标题行，如：6.2.2. Powder metallurgy
    #
    # 最终，如果是有用信息输出：True；无用信息输出：False
    # '''
    #
    # with open("expanded.json", "r", encoding="utf-8") as f:
    #     expanded = json.load(f)
    #
    # for i in range(len(expanded)):
    #     content = expanded[i]['Content']
    #     messages=[
    #             {"role": "user", "content": prm},
    #             {"role": "assistant", "content": "当然，请提供相关段落，我会帮你判断是否有用。"},
    #             {"role": "user", "content": content},
    #         ]
    #     expanded[i]['AI Effective Information Evaluation'] = chat.generate(messages, stream=False)
    #
    # with open("expanded_Evaluation.json", "w", encoding="utf-8") as f:
    #     json.dump(expanded, f, indent=4, ensure_ascii=False)
    # ************ 调用AI添加信息 ************** 结束

    # ************ 筛选信息 ************** 开始
    # # 筛选json
    # with open("expanded_Evaluation.json", "r", encoding="utf-8") as f:
    #     expanded = json.load(f)
    # filtered = []
    # field_name = "AI Effective Information Evaluation"
    # for item in expanded:
    #     value = str(item.get(field_name, ""))  # 获取字段内容，不存在则为空
    #     value = re.sub(r"<think>.*?</think>", "", value, flags=re.DOTALL)
    #     content = item.get("Content")  # 获取Content字段
    #
    #     # 筛选条件：field_name里不包含"false"，且Content不为空或None
    #     if "false" not in value.lower() and content not in (None, ""):
    #         new_item = item.copy()
    #         new_item.pop(field_name, None)  # 删除field_name字段
    #         filtered.append(new_item)
    # with open("expanded_field.json", "w", encoding="utf-8") as f:
    #     json.dump(filtered, f, indent=4, ensure_ascii=False)

    # 保存为MD
    # with open("expanded_field.json", "r", encoding="utf-8") as f:
    #     expanded = json.load(f)
    # keys_to_include = ["Article DOI","Article Title","Content position","Content"]
    # save_as_markdown(expanded, "expanded_field.md", keys_to_include=keys_to_include)
    # ************ 筛选信息 ************** 结束



