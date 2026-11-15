"""本地启动脚本

    python run.py            本机访问 http://127.0.0.1:8000
    python run.py 8123       换端口
    python run.py 8000 --lan 同一 Wi-Fi 下的同学也能加入（绑定 0.0.0.0）

不依赖 uvicorn 命令行的原因：比赛现场用哪个 Python 都不一定装好了 scripts。
"""
import os
import socket
import sys

import uvicorn


def lan_ips() -> list:
    """尽量列出本机能被同学访问到的 IPv4 地址。"""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))          # 不会真的发包，只为拿到出口网卡地址
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return ips


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    lan = "--lan" in sys.argv
    port = int(args[0]) if args else int(os.environ.get("PORT", "8000"))
    # 部署到云上时平台会给出 $PORT，并默认允许外部访问
    cloud = bool(os.environ.get("PORT"))
    host = "0.0.0.0" if (lan or cloud) else "127.0.0.1"

    print(f"圆桌 RoundTable 启动中…… 端口 {port}")
    if cloud:
        print("云端模式：平台给的外部地址就是入口")
    elif lan:
        print("局域网模式：把下面任一地址发给同一 Wi-Fi 下的同学")
        for ip in lan_ips():
            print(f"    http://{ip}:{port}")
    else:
        print(f"只允许本机访问：http://127.0.0.1:{port}")
        print("想让大家加入，加 --lan 参数重新启动")

    uvicorn.run("main:app", host=host, port=port, log_level="info")
