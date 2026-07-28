# 航電系統 LoRa 無線通訊測試平台技術文件

本文件詳細記錄 `P2026_rfTest` 專案的軟硬體架構、通訊協議與各模組的實作細節。本專案為航電系統主通訊與冗餘通訊鏈路的測試平台，包含 ESP32 韌體、LoRa 底層驅動、Python 管理工具、TCP 參數量測同步核心以及基於 Web/SSE 的即時遙測主控台。

---

## 一、 系統架構與硬體接線

本平台包含兩端：發射端（Transmitter / Sender）與接收端（Receiver）。硬體使用 ESP32 控制晶片配合 SX127x LoRa 模組。

### 1. 硬體版本與頻段模擬
* **915 MHz 冗餘鏈路**：
  * 地面端 (C 端)：Orion v5 電路板 + 915 MHz 定向八木天線。
  * 航電端 (D 端)：Orion v6 冗餘系統板 + 915 MHz 全向鞭狀天線。
* **433 MHz 主鏈路**：
  * 地面端 (A 端)：Orion v5 電路板 + 433 MHz 定向八木天線。
  * 航電端 (B 端)：航電主系統板 + 433 MHz 全向鞭狀天線。

### 2. SPI 與 GPIO 接線配置
Orion v5/v6 板與 ESP32 的連線定義完全一致，使用 VSPI 介面：

| 信號線 | ESP32 GPIO 腳位 | 說明 |
| :--- | :--- | :--- |
| **SCK** | GPIO 18 | SPI 時脈線 (VSPI 預設) |
| **MISO** | GPIO 19 | SPI 主入從出數據線 (VSPI 預設) |
| **MOSI** | GPIO 23 | SPI 主出從入數據線 (VSPI 預設) |
| **NSS (CS)** | GPIO 33 | SPI 片選腳 (主低電平有效) |
| **RST (Reset)** | GPIO 26 | LoRa 晶片硬體重置腳 |
| **DIO0 (IRQ)** | GPIO 13 | LoRa 中斷腳 (TxDone/RxDone) |

---

## 二、 韌體層實作邏輯 (`rfTestV6.cpp`)

韌體基於 Arduino 框架開發，採用狀態機模式管理測試流程。

### 1. 測試狀態機
系統定義了四種運行模式 (`enum Mode`)：
* `IDLE`：待機/接收模式。此時底層晶片維持在 `RXCONTINUOUS` 連續接收狀態。
* `PRE_TEST`：環境預測量模式。固定以 **SF7** 每 1 秒（1000ms）發射一個包，無限循環，用於微調天線指向。
* `FORMAL_TEST`：正式測試模式。依據所選 SF 自動設定發射安全間隔，限制發射 **100 個包**後自動切換回 `IDLE`。
* `STRESS_TEST`：壓力測試模式。由用戶自定義 SF 與發射間隔，限制發射 **100 個包**後自動切換回 `IDLE`。

### 2. 參數持久化儲存與 Flash 壽命防護 (Preferences)
韌體使用 ESP32 的非揮發性記憶體（Preferences 庫，命名空間 `"lora_cfg"`）保存當前配置。重啟後會自動讀取以下欄位：
* `freq` (long)：載波頻率（預設 915 MHz，當未手動指定時以 `#define LORA_FREQ` 為準）。
* `bw` (long)：信號頻寬（預設 125,000 Hz）。
* `cr` (int)：編碼率分母部分（預設 6，代表 CR 4/6）。
* `len` (int)：載荷長度（預設 255 Bytes）。
* `sf` (int)：接收/發射預設擴頻因子（預設 7）。

> [!IMPORTANT]
> **Flash 壽命防護與狀態一致性**：
> * **寫入防護**：只有當使用者設定的新參數值與記憶體中當前快取的值**不一致**時，才會呼叫 `prefs.putX` 寫入儲存媒體，防止 Flash 頻繁寫入。
> * **狀態一致性修正**：對於 `v [SF]` 暫存指令，為了防範測試中暫時修改 `currentSF` 導致快取值與 NVS 不一致，程式碼採用了「寫入前讀取 NVS 原值 (`prefs.getInt("sf")`)」進行比對，確保在斷電重啟後參數仍能正確恢復。

### 3. 發射安全間隔機制
為避免在高 SF 模式下，發射間隔小於空氣傳輸時間（ToA, Time on Air）造成發射緩衝區溢出，`getSafeInterval(int sf)` 提供以下防呆間隔：
* **SF6 - SF7**：250 ms
* **SF8**：500 ms
* **SF9**：1000 ms
* **SF10**：2000 ms
* **SF11 - SF12**：5000 ms

### 4. 封包格式與最小長度防呆
發射的 Payload 格式如下：
`[模式前綴]:[封包序號]:[當前測試 UUID][*填滿字元]`
* 模式前綴：`PRE_TEST` 使用 `TST:`；`FORMAL_TEST` 使用 `FRM:`；`STRESS_TEST` 使用 `STR:`。
* 封包序號：自增計數器（0 到 99）。
* 填滿字元：使用 `*` 填充至目標載荷長度（`targetPayloadLength`），最長支援 255 內容，以模擬真實長包數據的鏈路效能。

> [!WARNING]
> **最小長度防呆**：由於發送基本格式包含 `[前綴] + [ID] + [UUID]`，其物理長度已達到 43 Bytes。為了防止雙端在 SF6 隱含標頭模式下，因為發射長度大於接收期望長度（`expected_length`）導致解調失敗，**載荷長度指令 `l [Len]` 的最小限制被嚴格設為 45 級別**（限制範圍：45 - 255 Bytes）。

### 5. 序列埠控制指令表
當在 IDLE 接收狀態或發射狀態時，可通過 115200 Baud Rate 的 Serial 埠向 ESP32 發送控制指令：

| 指令 | 說明 | 範例與限制 |
| :--- | :--- | :--- |
| `f [Hz]` | 設定頻率並寫入 Prefs | `f 915000000` |
| `b [Hz]` | 設定頻寬並寫入 Prefs | `b 125000` |
| `c [CR]` | 設定編碼率分母並寫入 Prefs | `c 6` (CR = 4/6) |
| `l [Len]` | 設定載荷長度並寫入 Prefs | `l 255` (範圍 45-255 區間) |
| `v [SF]` | 設定接收端擴頻因子並寫入 Prefs | `v 7` (範圍 6-12) |
| `r` | 重置統計數據 (僅列印通知) | `r` |
| `u [UUID]` | 設定當前測試工作會話 UUID | `u 550e8400-e29b-41d4-a716-446655440000` |
| `p` 或 `p [SF]` | 啟動環境預測量測試 | `p` (預設 SF7) 或 `p 8` |
| `6` ~ `12` | 以指定 SF 啟動正式測試 (100 包) | `7` |
| `s [SF] [Interval]` | 啟動壓力測試 | `s 8 150` (SF8，間隔 150ms) |
| `x` | 停止發射，重設為接收狀態 | `x` |

---

## 三、 LoRa 暫存器驅動實作 (`LoRaDriver.cpp`)

驅動模組棄用第三方庫，使用 ESP-IDF 的 `spi_master.h` 直接控制 SX127x 暫存器。

### 1. SPI 通訊底層
* 速度：9 MHz
* 模式：SPI Mode 0
* 封包傳輸：
  * 讀取暫存器：發送 `(reg & 0x7F)` + `0x00`，在第二個 byte 接收資料。
  * 寫入暫存器：發送 `(reg | 0x80)` + `val`。

### 2. 核心暫存器映射與控制

#### A. 擴頻因子與標頭模式控制 (`lora_set_spreading_factor`)
* **SF6 限制與隱含標頭 (Implicit Header)**：
  * 當 `sf == 6` 時，必須啟用隱含標頭模式，且底層驅動寫入 `0x1D` 暫存器之 `0x01` 位元（啟用 Implicit Header）。
  * 同時必須寫入 **`DetectOptimize` (0x31)** 暫存器為 `0xC5`，以及 **`DetectionThreshold` (0x37)** 暫存器為 `0x0C` 以優化 SF6 的接收敏感度。
  * 對於接收端，在接收 SF6 包時，必須傳入合法的 `expected_length` 參數寫入 `0x22`（RegPayloadLength），否則晶片將無法解調並觸發 `RxDone`。
  
  > [!WARNING]
  > **SF6 關鍵限制**：在隱含標頭 (Implicit Header) 模式下，接收端不讀取無線封包中的長度欄位，而是直接套用 `expected_length`。**因此雙端（發射端與接收端）的封包長度設定必須嚴格保持一致，否則封包將在物理層直接被丟棄**，且不會觸發任何 CRC 或接收錯誤。

* **SF7-SF12 與顯含標頭 (Explicit Header)**：
  * 驅動將 `0x1D` 的最低位清零（Explicit Header）。
  * 寫入 **`DetectOptimize` (0x31)** 為 `0xC3`，以及 **`DetectionThreshold` (0x37)** 為 `0x0A`。

#### B. 低數據率優化 (Low Data Rate Optimize)
* 當設置之 `sf >= 11` 時，`RegModemConfig3 (0x26)` 暫存器的第 3 位（`LowDataRateOptimize`）必須設為 `1`。否則，因擴頻時間過長，頻率偏移會導致解調失敗。

#### C. AGC 自動增益 (AgcAutoOn)
* 在寫入 `0x26` 時，始終保持第 2 位為 `1` 啟用 `AgcAutoOn`。

#### D. PA 發射功率控制 (`lora_set_tx_power`)
* 晶片支援高功率發射（最高 20 dBm）：
  * 當目標功率為 2-17 dBm：設定輸出源為 `PA_BOOST`（寫入 `0x09` 暫存器之 `0x80 | (level - 2)`），並設定 `RegPaDac (0x4D)` 為普通模式 `0x84`。
  * 當目標功率為 18-20 dBm：設定功率級別為 `level - 3`，並設定 `RegPaDac (0x4D)` 為高增益模式 `0x87`。

#### E. 接收狀態與 RSSI / SNR 讀取
* **RSSI 讀取**：
  * SX127x 回傳的暫存器 `0x1A` 原始數值需減去偏移量。對於高頻段（868/915 MHz），典型公式為 `RSSI = RegPacketRssi - 157`。
* **SNR 讀取**：
  * 暫存器 `0x1B` 的數值為補數格式。公式為 `SNR = ((int8_t)RegPacketSnr) * 0.25`。

---

## 四、 Python 管理端與控制層

Python 端是整個測試平台的控制大腦，負責串口讀寫、OTA 燒錄、遙測解析、TCP 同步與 Web API 提供。

### 1. 串口自動燒錄與 PlatformIO 整合
* 腳本執行 `Flash Firmware` 時，會自動建立並清理 `src/` 目錄，將 `rfTestV6.cpp` 拷貝至 `src/` 目錄。
* 執行子程序命令 `pio run -t upload --upload-port [Port]`（在 Pixi 環境下為 `pixi run upload`）完成全自動編譯及燒錄。

### 2. 雙端 TCP 參數量測同步核心 (`tcp_sync.py`)
`TCPSyncManager` 提供雙機自動化參數對齊功能：
* **伺服器端**：在背景開啟監聽線程（預設連接埠 `50077`，若被占用則以 +1 遞增嘗試最高 10 次）。
* **客戶端**：可主動連接對端 IP（如 Tailscale IP）建立雙向 TCP 通道。
* **同步邏輯與執行緒安全**：
  * 當發射端更改參數或啟動測試時，會透過 TCP 將對應命令發送至接收端，由接收端的背景執行緒寫入對應的串口。
  * **執行緒安全鎖 (serial_lock)**：為避免背景 TCP 執行緒在進行串口寫入時，與主執行緒的關閉/重設串口行為衝突，專案導入了 `serial_lock`。所有對 `ACTIVE_SERIAL` 的寫入與關閉作業均在此互斥鎖保護下安全進行，防範跨執行緒 Null 指針與競爭危害。

### 3. 丟包統計與會話生命週期管理
在接收端 Data Logger 模式中，為了防止多輪測試數據混淆，Python 端設計了基於 UUID 的會話隔離統計：
* **會話字典**：以 `UUID` 為 Key，記錄 `{"received_ids": set(), "max_id": int, "snr_sum": float, "rssi_sum": float, "count": int}`。
* **重置檢測**：若收到的 packet ID 小於當前最大 `max_id - 5` 或收到 ID 為 0 且最大 ID 大於 0，表示發射端重設或重新開始了新一輪測試。Python 會自動重設該 UUID 的統計值。
* **丟包率公式**：
  $$\text{Loss Rate} = \frac{({\text{max\_id} + 1}) - \text{len(received\_ids)}}{\text{max\_id} + 1} \times 100\%$$
* **動態日誌切換**：當檢測到 Payload 中的 UUID 改變時，Data Logger 會自動關閉舊日誌，並以當前頻率、SF 和新 UUID 為名建立新的 CSV 檔案（路徑：`logs/received_packets_[Freq]MHz_SF[SF]_[UUID].csv`）。

### 4. 跨平台單執行緒字元級非阻塞輸入機制
專案完全屏棄了背景 `sys.stdin` 監聽執行緒（原本的 Windows 專屬版 `rf_test_manager_w.py` 已完全被廢棄與移除，本主程式已統一跨平台相容）：
* **單執行緒輪詢與微秒級 timeout**：串口讀寫的 `timeout` 被調降為 `0.05` 秒 (50ms)。在主迴圈每次迭代中，輪詢式調用字元級非阻塞輸入函數。
* **跨平台實作**：
  * **UNIX/macOS**：利用 `select` 檢查標準輸入是否有資料，隨後切換至字元級 `cbreak` 模式（透過 `termios` 和 `tty` 設定）讀取單個字元並立刻恢復終端設定。這實現了真正字元級的非阻塞，防止使用者輸入一半時造成主執行緒卡死。
  * **Windows**：調用 Windows 專屬的 `msvcrt.kbhit()` 偵測鍵盤按鍵，並透過 `msvcrt.getch()` 讀取，結合緩衝區組裝為完整的命令行，並過濾掉箭頭鍵等控制字元 (以 `b'\xe0'`, `b'\x00'` 為特徵的雙字節按鍵)。
* 此機制確保了程式在終止測試時能 100% 優雅回收資源，無任何殭屍執行緒残留，且程式碼完全跨平台相容。

---

## 五、 Web 即時遙測與控制伺服器

Web 伺服器整合在 `web_server.py` 中，提供前後端分離的遠端測試面板。

### 1. REST API
* `POST /api/control`：控制指令接收埠。支援參數：
  * `action`: `'send_command'`, `'connect_peer'`, `'disconnect_peer'`, `'send_command_sync'`, `'apply_settings'`, `'start_test'` 等。
* `GET /api/status`：獲取當前系統狀態，包括：串列埠連線狀態、TCP 同步狀態、當前 SF/頻率、可用串口列表。

### 2. SSE (Server-Sent Events) API
* `GET /api/stream`：持久化 SSE 管道。
  * 每當 Python 從 Serial 讀取到原始資料，或解析出新的測試數據（Packet ID, SNR, RSSI, Loss%），都會封裝為 JSON 字串並通過 SSE 實時推送到所有連接的 Web 客戶端。

### 3. 前端儀表板 (`index.html`)
基於現代化設計美學構建的網頁端：
* **介面特色**：玻璃擬物化 (Glassmorphism)、深色模式優先、響應式佈局。
* **模組劃分**：
  * 測試基本資訊 (Overview) / 硬體接線 (Hardware)。
  * **交互測試矩陣 (Matrix)**：直觀展示 TRR 所有配置下的 RSSI, SNR, 丟包率表格，並提供手動填寫/導出。
  * **實時測試主控台 (Live Console)**：
    * 實時繪製 SNR / RSSI 的動態波形圖。
    * 提供視覺化控制滑桿（SF, Freq, BW, CR, Length）及「一鍵同步套用」按鈕。
    * 滾動日誌終端，以不同顏色標示發射（TX）、接收（RX）與 CRC 錯誤包。
