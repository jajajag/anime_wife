import numpy as np
import os
from io import BytesIO
from PIL import Image

def add_invisible_noise_content(content, noise_level=5):
    # 打开图片并转换为数组
    image = Image.open(BytesIO(content))
    
    # 如果图片是 RGBA 模式，则转换为 RGB
    if image.mode == 'RGBA':
        image = image.convert('RGB')
    
    image_array = np.array(image)
    
    # 生成随机噪声，范围为[-noise_level, noise_level]
    noise = np.random.randint(-noise_level, noise_level, image_array.shape, dtype='int16')
    
    # 将噪声添加到图像数据，并确保数据范围在[0, 255]
    noisy_image_array = image_array + noise
    noisy_image_array = np.clip(noisy_image_array, 0, 255).astype('uint8')
    
    # 将数组转换回图片
    noisy_image = Image.fromarray(noisy_image_array)
    out_buf = BytesIO()
    noisy_image.save(out_buf, format=image.format or 'JPEG', quality=90) # 调整保存质量
    
    return out_buf.getvalue()

def add_invisible_noise(image_path, output_path, noise_level=5):
    with open(image_path, 'rb') as f:
        content = f.read()
    noisy_content = add_invisible_noise_content(content, noise_level)
    with open(output_path, 'wb') as f:
        f.write(noisy_content)
    # 保存图片
    print(f"图片已处理并保存到 {output_path}")

def process_images_in_directory(input_dir, output_dir, noise_level=5):
    # 如果输出目录不存在，则创建它
    os.makedirs(output_dir, exist_ok=True)

    # 遍历输入目录中的所有文件
    for filename in os.listdir(input_dir):
        # 检查文件是否为图片文件
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            
            # 对图片添加噪声
            add_invisible_noise(input_path, output_path, noise_level)
            print(f"{filename} 已处理完成")

# 使用方法
input_directory = './wife'   # 替换为包含原图的目录路径
output_directory = './wife' # 替换为存储添加噪声图像的目录路径
process_images_in_directory(input_directory, output_directory, noise_level=5)
