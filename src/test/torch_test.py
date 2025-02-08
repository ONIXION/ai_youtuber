import torch

print(torch.__version__)

# GPUが利用可能かどうか確認
if torch.cuda.is_available():
    # デバイスをGPUに設定
    device = torch.device('cuda')
    print('GPUが利用可能です。')
else:
    # デバイスをCPUに設定
    device = torch.device('cpu')
    print('GPUが利用できません。')

# ランダムなテンソルを作成
x = torch.randn(100, 100, device=device)
y = torch.randn(100, 100, device=device)

# GPU上でテンソル計算を実行
z = x + y

# 結果を出力
print(z)
