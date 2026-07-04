# **航電系統 LoRa 無線通訊測試準備審查報告 (Test Readiness Review, TRR)**

本報告針對航電系統與其冗餘系統之無線通訊鏈路進行測試準備審查。本次測試選定於**社長家**與**望高寮**兩地進行實地視距（LOS）通訊測試，主要評估 433 MHz 與 915 MHz 頻段在 **SF7**、**256 Bytes 封包長度**下，八木天線（定向）與鞭狀天線（全向）在不同傳輸方向、常規對齊（0度）及極化偏角（30度/45度）下的通訊效能（RSSI、SNR、封包丟失率）。

## **一、 測試基本資訊**

* **測試專案**：航電主系統與冗餘系統 LoRa 遠距離實地通訊效能測試  
* **測試日期**：2026 年 6 月 27 日 (暫定)  
* **測試地點**：  
  * **基地台端 (A/C 端)**：社長家（配置八木天線 \+ Orion v5 電路板）  
  * **航電/冗餘端 (B/D 端)**：望高寮（配置鞭型天線 \+ 航電主系統 / Orion v6 冗餘系統）  
* **測試人員**：![][image1]  
* **審查狀態**：待審查 (Pending Review)

## **二、 測試硬體與系統配置**

本測試共涉及兩套獨立的通訊鏈路（433 MHz 與 915 MHz），分別模擬主系統與冗餘系統的實際運作場景：

### **1\. 硬體對象說明**

* **915 MHz 鏈路 (冗餘系統)**  
  * **地面端 (C 端)**：915 MHz 八木天線 (Yagi) \+ Orion v5 電路板（置於：**社長家**）。  
  * **航電端 (D 端)**：915 MHz 鞭狀天線 (Whip) \+ Orion v6 冗餘系統板（置於：**望高寮**）。  
* **433 MHz 鏈路 (主系統)**  
  * **地面端 (A 端)**：433 MHz 八木天線 (Yagi) \+ Orion v5 電路板（置於：**社長家**）。  
  * **航電端 (B 端)**：433 MHz 鞭狀天線 (Whip) \+ 航電主系統板（置於：**望高寮**）。

### **2\. 接線配置對照表**

| 硬體訊號線 (LoRa 模組) | ESP32 GPIO (Orion v5 - 社長家) | ESP32 GPIO (Orion v6 / 航電主系統 - 望高寮) | 備註 |
| :---- | :---- | :---- | :---- |
| **SCK** | GPIO 18 | GPIO 18 | VSPI 預設時鐘 |
| **MISO** | GPIO 19 | GPIO 19 | VSPI 預設數據輸入 |
| **MOSI** | GPIO 23 | GPIO 23 | VSPI 預設數據輸出 |
| **NSS / CS** | **GPIO 33** | **GPIO 33** | 片選訊號 (v5/v6 共用) |
| **RST (Reset)** | **GPIO 26** | **GPIO 26** | 晶片重置腳位 |
| **DIO0 (Interrupt)** | **GPIO 13** | **GPIO 13** | 中斷觸發腳位 |

## **三、 測試方法與項目矩陣 (依據測試紀錄表設計)**

本測試共包含 **4 大測試配置**。

每個配置在正常對位下進行 **6 次獨立重複測試**（每輪發射 **100 個封包**），並於 30 度與 45 度極化偏角下各進行 1 次測試。總計需收集與計算 32 組數據。

### **1\. 測試參數設定**

* **擴頻因子 (SF)**：固定為 **SF7**  
* **載荷長度 (Payload)**：固定為 **256 Bytes**（程式碼內預設已配置為 256，測試時亦可透過 l 256 指令重新確認）  
* **極化角度測試**：常規 6 次測試為 0° 對齊（垂直對垂直）。極化測試時將八木天線水平面旋轉 30° 與 45° 進行單次收發。

### **2\. 實測數據紀錄表 (Test Matrix)**

#### **【第一部分：915 MHz 鏈路測試 (SF7 / 256 Bytes)】**

##### **配置 1：社長家（八木） ![][image2] 望高寮（鞭型）**

| 評估指標 | No. 1 | No. 2 | No. 3 | No. 4 | No. 5 | No. 6 | 平均值 (Avg) | 極化：30° | 極化：45° |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **丟包率 (%)** |  |  |  |  |  |  |  |  |  |
| **SNR (dB)** |  |  |  |  |  |  |  |  |  |
| **RSSI (dBm)** |  |  |  |  |  |  |  |  |  |

##### **配置 2：社長家（八木） ![][image3] 望高寮（鞭型）**

| 評估指標 | No. 1 | No. 2 | No. 3 | No. 4 | No. 5 | No. 6 | 平均值 (Avg) | 極化：30° | 極化：45° |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **丟包率 (%)** |  |  |  |  |  |  |  |  |  |
| **SNR (dB)** |  |  |  |  |  |  |  |  |  |
| **RSSI (dBm)** |  |  |  |  |  |  |  |  |  |

#### **【第二部分：433 MHz 鏈路測試 (SF7 / 256 Bytes)】**

##### **配置 3：社長家（八木） ![][image2] 望高寮（鞭型）**

| 評估指標 | No. 1 | No. 2 | No. 3 | No. 4 | No. 5 | No. 6 | 平均值 (Avg) | 極化：30° | 極化：45° |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **丟包率 (%)** |  |  |  |  |  |  |  |  |  |
| **SNR (dB)** |  |  |  |  |  |  |  |  |  |
| **RSSI (dBm)** |  |  |  |  |  |  |  |  |  |

##### **配置 4：社長家（八木） ![][image3] 望高寮（鞭型）**

| 評估指標 | No. 1 | No. 2 | No. 3 | No. 4 | No. 5 | No. 6 | 平均值 (Avg) | 極化：30° | 極化：45° |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **丟包率 (%)** |  |  |  |  |  |  |  |  |  |
| **SNR (dB)** |  |  |  |  |  |  |  |  |  |
| **RSSI (dBm)** |  |  |  |  |  |  |  |  |  |

## **四、 測試操作步驟說明**

為了確保測試流程順利且數據能自動紀錄（包含 UUID 追蹤），請務必使用專案內的 `rf_test_manager.py` 腳本進行操作：

1. **韌體燒錄與頻率配置 (選項 2)**：
   * 確保天線均已接妥。
   * 執行 `rf_test_manager.py` 並選擇 **2) Flash Firmware**。
   * 依序選擇「燒錄板子類型 (Sender/Receiver)」、「硬體版本 (Orion v5/v6)」，以及「載波頻率 (433MHz/915MHz)」。腳本將自動修改頻率並透過 PlatformIO 完成編譯與燒錄。
2. **對位預測量 (選項 3 與 選項 4)**：
   * 接收端選擇 **4) Run Receiver Data Logger** 進入監聽與自動紀錄模式。
   * 發射端選擇 **3) Start Transmitter**，並於測試模式選單中選擇 **3) Pre-Test** 進入環境預測模式。
   * 根據接收端回傳的 RSSI 微調天線指向，獲得最大信號強度後，發射端輸入 `x` 停止預測。
3. **常規 6 次測試 (No.1 - No.6)**：
   * 接收端保持在 Data Logger 監聽模式。
   * 發射端在選單中選擇 **1) Formal Test** 並輸入 **7** 啟動 SF7 (100 包) 測試。
   * 發射完畢後，腳本會自動將接收到的 Loss%、RSSI 與 SNR 以及 UUID 記錄到 CSV 日誌中。
   * **重複此步驟 6 次**。每次測試開始前，可於接收端終端機輸入 `r` 重置統計（測試程式亦會透過 UUID 變化自動重置統計）。
4. **極化偏角測試 (30° / 45°)**：
   * 旋轉鞭型天線之極化角至對應角度。
   * 發射端再次啟動 **Formal Test** (SF7)。
   * 測試結束後確認 CSV 日誌中的數據。

## **五、 離心力與震動模擬測試 (洗衣機模擬)**

依據 **《DAWNSEEK Avionics Subsystem CDR》** 之 6-2-3 與 FMEA，火箭發射時會承受極大軸向加速度與高頻震動。本測試將利用洗衣機之脫水功能模擬高 G 值環境，確保硬體不會損壞或假焊。

### **1. 測試設備**
* **被測物**：航電段 (PETG 結構、電路板、電池、SD 卡)。
* **測試載體**：直立式/滾筒式洗衣機 (使用單獨脫水模式)。
* **緩衝與固定**：高密度海綿/厚毛巾、強力膠帶。
* **配重物**：與被測物等重之沙袋或水瓶 (極度關鍵)。

### **2. 理論 G 值換算**
* 公式：$a = R \\cdot \\omega^2$
* 假設洗衣機脫水槽半徑 $R = 0.25$ 公尺，400 RPM 時約產生 **44 G** 的離心加速度，完全涵蓋探空火箭升空時的 10G ~ 30G 需求。

### **3. 操作步驟**
1. **結構整備**：將線束沿固定點綁緊，鎖妥 XT30 電源接頭與 M3 熱熔螺母。
2. **防護與固定**：用毛巾包覆航電段，並將其用強力膠帶死死固定於洗衣機內槽**最邊緣 (筒壁)**，確保 Z 軸指向筒壁外。
3. **配重平衡**：**必須在 180 度對角線位置，綁上等重的水瓶進行平衡**，避免洗衣機解體。
4. **啟動測試**：開啟航電進入飛行紀錄模式，確認 SD 卡正常寫入。啟動洗衣機脫水模式 (低轉速) 運行 1~3 分鐘。
5. **驗收標準**：
   * 檢查結構無裂紋，電子元件 (MCU、LoRa)、XT30、SD卡槽無鬆動假焊。
   * 檢查 SD 卡紀錄之 IMU 數據無中斷，且系統未因短路而發生斷電重啟。

## **六、 測試原始程式碼備份**

### **1\. 發射端代碼 (Sender.ino)**

*已整合 LORA\_FREQ 防呆頻率切換與支援最大 256 Bytes 封包長度。*

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABUAAAAZCAYAAADe1WXtAAAA20lEQVR4Xr2STQrCMBCFGxBExHVdlEwXlYBHcOmFPIgX8ViCtxBRJ8T+zUtsa1I/MgTezLyZhmbZ3Cgp/I3O5MglItuR0GrJB83C4JauYLCsgyZ6SS0arfUlz/O11C1TlnN8OqpdtSSiay+XAmPMho3vUm8g0gcu8ERIb+LIcSuKYiU97RudekHuJql7gk0fXL93TvCiIAxCUX+BZx4bPvlaSH0irTMbnsuy3GLmR6zByM9W9QHZR18OFKUERihQEIVt47Bt4dY6426sQ6XlWy45k4dBAwiogDATb6RYI/s6j0FWAAAAAElFTkSuQmCC>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAdCAYAAACwuqxLAAAA/UlEQVR4Xq2TTRKCMAyF4QouHaBwCXfewWu5ceF4PE/geAdNEUubv6bQbyYjvLyXVIWmUWix4JnFtMP6UooDC3anicrjdrL7NNkB7d+SdVYi3mPcabRRnHMv/ykPkDsUxgsL3lj7EZmZnIlxHK993x+xnif8qTJd1x3g9E+sV2GappMb+J8me7IccOoH1AfqDnULNUTXbA3hOhkovQB+CdZiSMDCHIqS0pJgEbYIMgWeoDM8SRdzYAv8tyhbaXRTG1UUTGbWxIoBvbugmUiPCJUonrsGiqMC0Rw8Et+rFJlrsHUhzuF7GbtT92q9YuZhGyaaIllT1uDRTXp35QuY+B0XicZO4QAAAABJRU5ErkJggg==>