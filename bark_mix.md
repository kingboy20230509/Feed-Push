 "proxy_file": "./local_proxies.txt" 文件格式应按例子所示：
```
账号:密码@ip:端口
admin:password@1.2.3.4:1234
1.2.3.4:1234
```
 
### **1. 准备工作**
#### 更新系统：
```
sudo apt update && sudo apt upgrade -y
```
#### 安装 Python 和工具：
```
sudo apt install python3 python3-pip python3-venv -y
```
---
### **2. 设置项目目录**

#### 创建项目目录：
```
mkdir /home/Python_project/bark_mix/ && cd /home/Python_project/bark_mix/
```
#### 创建虚拟环境：
**虚拟环境**就像给你的 Python 项目一个单独的小空间，用来装它自己需要的工具和材料，避免跟别的项目或者系统的工具混在一起，产生冲突。
```
python3 -m venv venv
```
#### 激活虚拟环境：
```
source venv/bin/activate
```
---
### **3. 安装依赖**
在虚拟环境中，运行以下命令安装所需依赖：
```
pip install feedparser requests urllib3
```
---
### **4. 添加脚本文件**
#### 创建脚本文件：
```
nano bark_mix.py
```
#### 在文件中添加脚本内容（你已经提供的代码）。
**保存并退出**： 按 `Ctrl+O` 保存，按 `Ctrl+X` 退出。
---
### **5. 测试运行脚本**

#### 激活虚拟环境（如果未激活）：
```
source venv/bin/activate
```
#### 运行脚本：
```
python bark_mix.py
```

**观察脚本是否运行正常**：
- 如果没有错误，继续下一步。
- 如果有错误，请检查错误日志并修复。
ctrl+c  停止运行
---
### **6. 创建 `systemd` 服务**
#### 创建服务文件：
```
sudo nano /etc/systemd/system/bark_mix.service
```
#### 添加以下内容到文件：
```
[Unit]
Description=Bark Mix RSS
After=network.target

[Service]
User=root
WorkingDirectory=/home/Python_project/bark_mix
ExecStart=/home/Python_project/bark_mix/venv/bin/python /home/Python_project/bark_mix/bark_mix.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```
**注意**：
- **`WorkingDirectory`**：项目所在目录。
- **`ExecStart`**：虚拟环境中的 Python 和脚本路径。
- **`Restart=always`**：脚本异常退出时会自动重启。
**保存并退出**：按 `Ctrl+O` 保存，按 `Ctrl+X` 退出。
---
### **7. 启动服务**
#### 重新加载 `systemd` 配置：
```
sudo systemctl daemon-reload
```
#### 启动服务：
```
sudo systemctl start bark_mix
```
#### 设置开机启动：
```
sudo systemctl enable bark_mix
```
---
### **8. 检查服务状态**
#### 查看服务状态：
```
sudo systemctl status bark_mix
```
你应该看到类似以下的输出：

```
● bark_mix.service - Bark Mix RSS

   Loaded: loaded (/etc/systemd/system/bark_mix.service; enabled; vendor preset: enabled)
   Active: active (running) since <时间戳>
     Docs: <描述或文档>
 Main PID: <PID> (<主进程>)
    Tasks: <任务数>
   Memory: <内存使用情况>
      CPU: <CPU使用情况>
   CGroup: /system.slice/bark_mix.service
           └─<PID> python3 /path/to/bark_mix.py
```

---
### **服务管理命令**
- **启动服务**：
```
sudo systemctl start bark_mix
```
- **停止服务**：
```
sudo systemctl stop bark_mix
```
- **重启服务**：
```
sudo systemctl restart bark_mix
```
- **查看服务状态**：
```
sudo systemctl status bark_mix
```
- **实时查看服务日志**：
```
journalctl -u bark_mix -f
```
---
修改脚本后
```
sudo systemctl restart bark_mix && sudo systemctl status bark_mix
```
