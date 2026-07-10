#include <Arduino.h>
#include "LoRaDriver.hpp"

// =================================================================
// 測試載波頻率配置（接收端需與發射端保持頻段同步）
// =================================================================
#define LORA_FREQ   433E6   // 433 MHz 鏈路：配置 3 & 配置 4
//#define LORA_FREQ      915E6   // 915 MHz 鏈路：配置 1 & 配置 2

int currentSF = 7;
int targetPayloadLength = 255; // SF6 必須提前約定封包長度

void updateParams(int sf);

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000); // 針對具備 Native USB 的型號提供保護
  delay(500); // 確保 Serial 硬體與主機端連線穩定
  while (Serial.available() > 0) {
    Serial.read(); // 清除開機時產生的雜訊與快取殘留數據
  }
  Serial.setTimeout(50); // 縮短超時時間，避免雜訊導致 loop 長時間阻塞

  Serial.print("\n=== LoRa 接收端初始化 [頻率: ");
  Serial.print(LORA_FREQ / 1E6);
  Serial.println(" MHz] ===");

  lora_init(LORA_FREQ);
  
  lora_set_bandwidth(125000);
  lora_set_coding_rate(6);
  lora_set_preamble_length(12);
  lora_set_sync_word(0xF1);
  lora_enable_crc();      // 【盲點修復】開啟硬體 CRC 攔截損壞的 RF 封包
  
  updateParams(7);

  Serial.println("\n--- ESP32 接收端指令 ---");
  Serial.println("  f [Hz]     : 設定頻率 (例如 f 915000000)");
  Serial.println("  b [Hz]     : 設定頻寬 (例如 b 125000)");
  Serial.println("  c [CR]     : 設定編碼率分母 (例如 c 6 表示 4/6)");
  Serial.println("  l [Len]    : 設定封包長度 (預設 256 Bytes)");
  Serial.println("  p          : 同步至 SF7");
  Serial.println("  7-12       : 同步至目標 SF");
  Serial.println("  r          : 重置統計數據");
}

void loop() {
  // 處理序列埠指令
  if (Serial.available()) {
    String in = Serial.readStringUntil('\n'); 
    in.trim();
    if (in == "p") {
      updateParams(7);
    }
    else if (in == "r") {
      Serial.println(">>> RESET");
    }
    else if (in.startsWith("l ")) {
      int len = 0;
      if (sscanf(in.c_str(), "l %d", &len) == 1) {
        if (len >= 10 && len <= 255) {
          targetPayloadLength = len;
          Serial.print("\n>>> [設定] 目標封包長度已更改為: "); 
          Serial.print(targetPayloadLength); Serial.println(" Bytes");
        } else {
          Serial.println(">>> 參數錯誤：長度需介於 10 到 255 Bytes 之間");
        }
      }
    }
    else if (in.startsWith("f ")) {
      long freq = 0;
      if (sscanf(in.c_str(), "f %ld", &freq) == 1) {
        lora_idle();
        lora_set_frequency(freq);
        Serial.print("+SET_OK: Freq="); 
        Serial.print(freq / 1E6); Serial.println("MHz");
      }
    }
    else if (in.startsWith("b ")) {
      long bw = 0;
      if (sscanf(in.c_str(), "b %ld", &bw) == 1) {
        lora_idle();
        lora_set_bandwidth(bw);
        Serial.print("+SET_OK: BW="); 
        Serial.println(bw);
      }
    }
    else if (in.startsWith("c ")) {
      int cr = 0;
      if (sscanf(in.c_str(), "c %d", &cr) == 1) {
        lora_idle();
        lora_set_coding_rate(cr);
        Serial.print("+SET_OK: CR=4/"); 
        Serial.println(cr);
      }
    }
    else if (in.startsWith("v ")) {
      int sf = 0;
      if (sscanf(in.c_str(), "v %d", &sf) == 1) {
        if (sf >= 6 && sf <= 12) {
          updateParams(sf);
          Serial.print("+SET_OK: SF="); 
          Serial.println(sf);
        }
      }
    }
    else { 
      int v = in.toInt(); 
      if (v >= 6 && v <= 12) {
        updateParams(v);
      }
    }
  }
  
  // 處理 LoRa 接收封包
  uint8_t buf[256];
  int expected_length = (currentSF == 6) ? targetPayloadLength : 0;
  int packetSize = lora_receive(buf, sizeof(buf) - 1, expected_length);
  
  if (packetSize > 0) {
    buf[packetSize] = '\0';
    String data = String((char*)buf);
    
    float snr = lora_packet_snr();
    int rssi = lora_packet_rssi();

    Serial.print("+RCV:");
    Serial.print(data);
    Serial.print(" | SNR:");
    Serial.print(snr);
    Serial.print(" | RSSI:");
    Serial.println(rssi);
  } else if (packetSize < 0) {
    Serial.println("+RCV_ERR: CRC Error!");
  }
}

void updateParams(int sf) {
  currentSF = sf;
  lora_idle();
  lora_set_spreading_factor(sf);
  Serial.print(">>> 接收端同步至 SF"); Serial.println(sf);
}