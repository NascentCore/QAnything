import requests
import argparse

# 通用的 API 调用函数
def call_api(user_id, page_id=None, page_limit=None, save_to_excel=False, qa_ids=None):
    url = 'http://localhost:8777/api/local_doc_qa/get_qa_info'
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
        'Content-Type': 'application/json',
        'Cookie': 'loginSession=MTcwMjYxMDUzN3xEdi1CQkFFQ180SUFBUkFCRUFBQUt2LUNBQUVHYzNSeWFXNW5EQWtBQjJ4dloybHVTV1FHYzNSeWFXNW5EQXNBQ1VGdWIyNTViVzkxY3c9PXzKwgyedirwpU-RwrNZ3ReJFS13eniCo8IHfK25xs2-KQ==',
        'Origin': 'http://localhost:8777',
        'Referer': 'http://localhost:8777/qanything/?code=xxx',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    }

    # 根据不同的参数构建请求数据
    data = {
        "user_id": user_id,
        "save_to_excel": save_to_excel
    }
    if page_id and page_limit:  # 如果是获取 qa_ids
        data.update({"page_id": page_id, "page_limit": page_limit})
    if qa_ids:  # 如果是下载 Excel
        data.update({"qa_ids": qa_ids})

    # 发起 API 请求
    response = requests.post(url, headers=headers, json=data)

    # 如果是获取 qa_ids，返回 JSON 数据；如果是下载 Excel，返回二进制内容
    if save_to_excel:
        return response.content
    else:
        return response.json()

# 获取 qa_ids
def get_qa_info(page_limit):
    response_data = call_api(user_id="zzp", page_id=1, page_limit=page_limit)

    # 获取 qa_ids 列表
    qa_ids = [qa_info["qa_id"] for qa_info in response_data["qa_infos"]]
    return qa_ids

# 根据获取的 qa_ids 下载数据并保存到 Excel
def download_to_excel(qa_ids, filename):
    excel_data = call_api(user_id="zzp", save_to_excel=True, qa_ids=qa_ids)

    # 将返回的内容保存为 Excel 文件
    with open(filename, 'wb') as f:
        f.write(excel_data)
    print(f"数据已保存到 {filename}")

if __name__ == "__main__":
    # 使用 argparse 处理命令行参数
    parser = argparse.ArgumentParser(description="获取 qa_ids 并保存到 Excel 文件")
    parser.add_argument('-l', '--page_limit', type=int, default=1, help='每页的 qa_id 数量')
    parser.add_argument('-f', '--filename', type=str, default='xx.xlsx', help='保存的 Excel 文件名')

    args = parser.parse_args()

    # 获取 qa_ids
    qa_ids = get_qa_info(args.page_limit)

    # 保存数据到 Excel
    download_to_excel(qa_ids, args.filename)
