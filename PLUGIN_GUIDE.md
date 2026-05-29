# IST8310 Compass KittenBlock Plugin
## 安裝與使用說明

---

## 📦 插件安裝

### 方法一：直接 URL 安裝（推薦）

在 **kblock.kittenbot.cc** 中：
1. 點擊左下角 **「+」** 按鈕（新增插件）
2. 選擇 **「From URL」** 或 **「外部插件」**
3. 輸入以下 URL：

```
https://gmiiliao.github.io/futureboardai-ist8310-compass/IST8310Compass.zip
```

4. 點擊確認，插件會自動安裝

---

### 方法二：本機 zip 安裝

下載 zip 文件後，在 KittenBlock 中：
1. 點擊 **「+」** → **「From File」**
2. 選擇 `IST8310Compass.zip`

---

## 🔌 連接未來板

插件安裝後，在積木欄中選擇 **「IST8310 羅盤」**：

### 方法 A：USB 串口連接（Chrome/Edge 瀏覽器）
```
[連接 IST8310 羅盤 (USB串口)]
```
- 需要使用 Chrome 或 Edge 瀏覽器（支援 WebSerial API）
- 點擊積木後，選擇 **未來板AI** 的串口

### 方法 B：KittenBlock 設備連接
```
[連接 IST8310 羅盤 (KittenBlock設備)]
```
- 先在 KittenBlock 中連接未來板（選擇未來板AI設備）
- 再點擊此積木

---

## 🧭 積木說明

### 連接設置
| 積木 | 說明 |
|------|------|
| 連接 IST8310 羅盤 (USB串口) | 透過 WebSerial 連接 |
| 連接 IST8310 羅盤 (KittenBlock設備) | 透過 KittenBlock 設備連接 |
| 羅盤已連接? | 回傳 true/false |
| 斷開連接 | 中斷連接 |

### 羅盤航向
| 積木 | 說明 |
|------|------|
| 更新羅盤數據 | 手動刷新數據 |
| 航向角度 (°) | 回傳 0-360° |
| 羅盤方向 | 回傳 N/NE/E/SE/S/SW/W/NW |
| 正在朝向 [DIR] ? | 布林值，可選 8 個方向 |
| 航向在 [MIN]° 和 [MAX]° 之間? | 範圍判斷 |

### 磁場數據 (µT)
| 積木 | 說明 |
|------|------|
| 磁場 X (µT) | IST8310 X 軸磁場值 |
| 磁場 Y (µT) | IST8310 Y 軸磁場值 |
| 磁場 Z (µT) | IST8310 Z 軸磁場值 |
| 磁場強度 (µT) | 總磁場強度 |

### 姿態角度
| 積木 | 說明 |
|------|------|
| 俯仰角 Pitch (°) | 前後傾斜角度 |
| 橫滾角 Roll (°) | 左右傾斜角度 |

### 校準
| 積木 | 說明 |
|------|------|
| 開始磁場校準 | 同時按未來板 A 鍵 |
| 完成校準並儲存 | 同時按未來板 B 鍵 |

---

## 📝 使用範例

### 基本範例：顯示航向

```scratch
當 ▶ 被點擊
連接 IST8310 羅盤 (USB串口)
重複執行
  更新羅盤數據
  說 (航向角度 (°)) 秒 (0.3)
```

### 進階範例：方向提示

```scratch
當 ▶ 被點擊
連接 IST8310 羅盤 (USB串口)
重複執行
  更新羅盤數據
  如果 <正在朝向 [北 (N)]?> 那麼
    說 "面向北方！" 1 秒
  結束
```

---

## ⚙️ 磁場校準步驟

1. 執行 `[開始磁場校準]` 積木（或按未來板 A 鍵）
2. 慢慢旋轉未來板，朝各個方向（8字形動作）
3. 執行 `[完成校準並儲存]` 積木（或按未來板 B 鍵）
4. 校準偏移量自動儲存

---

## 🔧 硬體需求

| 項目 | 規格 |
|------|------|
| 主控器 | 未來板 AI (FutureLite ESP32-S3-FN8) |
| 感測器 | IST8310 磁力計模組 |
| 連接方式 | I2C (SCL=GPIO1, SDA=GPIO2) |
| I2C 地址 | 0x0E |
| 瀏覽器 | Chrome / Edge（需支援 WebSerial API） |

---

## 📁 文件結構

```
IST8310Compass.zip
├── index.js          # 插件主程式
├── extension.json    # 插件元數據
└── compass_icon.png  # 插件圖標
```

---

## 🔗 相關連結

- **GitHub 倉庫**: https://github.com/GmiiLiao/futureboardai-ist8310-compass
- **插件下載**: https://gmiiliao.github.io/futureboardai-ist8310-compass/IST8310Compass.zip
- **KittenBlock**: https://kblock.kittenbot.cc
