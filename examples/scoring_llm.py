import os
import pandas as pd
import argparse
from openai import OpenAI, AsyncOpenAI

def get_openai_client(api_key, base_url=None):
    # 根据是否有 base_url 来决定是普通 OpenAI 还是带有 URL 的版本
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    else:
        return OpenAI(api_key=api_key)

def score_answers(excel_file, model_name, api_key, base_url=None):
    client = get_openai_client(api_key, base_url)
    df = pd.read_excel(excel_file)

    # 新增列
    df['准确度得分'] = None
    df['综合得分'] = None
    df['打分依据'] = None

    print(f"问题\t准确度得分\t综合得分\t打分依据")

    for index, row in df.iterrows():
        question = row['问题']
        reference_answer = row['参考答案']
        knowledge_answer = row['知识库答案']

        answers_txt = f"问题：\n{question}\n参考答案：\n{reference_answer}\n知识库答案：\n{knowledge_answer}"

        content = answers_txt + "\n请对上面的参考答案和知识库答案进行打分，语义上只要知识库答案覆盖了参考答案就得满分（10分满分），在这个分数基础上，从冗余信息、输出格式、关键字缺失等角度适当减分，得出一个综合得分，按以下格式直接输出你的答案：{问题}\t{准确度得分}\t{综合得分}\t{打分依据}"

        # 构造请求
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": content}
            ],
            temperature=0.7
        )

        result = response.choices[0].message.content
        print(result)

        # 假设返回的结果格式是：{问题}\t{准确度得分}\t{综合得分}\t{打分依据}
        # 解析返回的结果
        try:
            parts = result.split("\t")
            if len(parts) == 4:
                df.at[index, '准确度得分'] = parts[1]
                df.at[index, '综合得分'] = parts[2]
                df.at[index, '打分依据'] = parts[3]
        except Exception as e:
            print(f"Error parsing result for index {index}: {e}")
            df.at[index, '准确度得分'] = "N/A"
            df.at[index, '综合得分'] = "N/A"
            df.at[index, '打分依据'] = "Error"

    # 将结果保存回 Excel 文件
    df.to_excel(excel_file, index=False)
    print(f"Updated Excel file saved as {excel_file}")

def main():
    parser = argparse.ArgumentParser(description="评分脚本")
    parser.add_argument("--api_key", required=True, help="DOUBAO API Key")
    parser.add_argument("--excel_file", default="results_for_doubao.xlsx", help="输入的 Excel 文件")
    parser.add_argument("--model", choices=["ep-20240721110948-mdv29", "gpt-4o"], required=True, help="选择模型")
    parser.add_argument("--base_url", help="DOUBAO API URL (可选)")

    args = parser.parse_args()

    score_answers(args.excel_file, args.model, args.api_key, args.base_url)

if __name__ == "__main__":
    main()
