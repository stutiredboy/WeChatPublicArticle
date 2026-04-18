import zipfile
import os

source_dir = '/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle/2026/02/insurance_article/'
output_zip = '/home/tiredboy/.nanobot/workspace/repos/WeChatPublicArticle/2026/02/insurance_article.zip'

with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            # 只打包文章和图片，排除脚本文件
            if file.endswith(('.md', '.html', '.png')):
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, source_dir))

print(f"Zip created at {output_zip}")
