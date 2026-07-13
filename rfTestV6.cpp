#include <Arduino.h>
#include "LoRaDriver.hpp"
#include <Preferences.h>

Preferences prefs;

// =================================================================
// 測試載波頻率配置（請依據當下測試配置切換註解，再進行燒錄）
// =================================================================
//#define LORA_FREQ   433E6   // 433 MHz 鏈路：配置 3 & 配置 4
#define LORA_FREQ      915E6   // 915 MHz 鏈路：配置 1 & 配置 2

enum Mode { IDLE, PRE_TEST, FORMAL_TEST, STRESS_TEST };
Mode currentMode = IDLE;
int currentSF = 7;
unsigned long testInterval = 500; 
unsigned long packetCounter = 0;
unsigned long lastSendTime = 0;
const int packetLimit = 100;
int targetPayloadLength = 255; 
String currentUUID = "N/A";    

void handleSerial();
void sendPacket();
void updateParams(int sf);
void printMenu();
unsigned long getSafeInterval(int sf); 

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000); 
  delay(500); 
  while (Serial.available() > 0) {
    Serial.read(); 
  }
  Serial.setTimeout(50); 
  
  prefs.begin("lora_cfg", false);
  long saved_freq = prefs.getLong("freq", LORA_FREQ);
  long saved_bw = prefs.getLong("bw", 125000);
  int saved_cr = prefs.getInt("cr", 6);
  int saved_len = prefs.getInt("len", 255);
  int saved_sf = prefs.getInt("sf", 7);
  
  targetPayloadLength = saved_len;

  Serial.print("\n=== LoRa 整合測試端初始化 [頻率: ");
  Serial.print(saved_freq / 1E6);
  Serial.println(" MHz] ===");

  lora_init(saved_freq);
  
  lora_set_bandwidth(saved_bw);
  lora_set_coding_rate(saved_cr);
  lora_set_preamble_length(12);
  lora_set_sync_word(0xF1);
  lora_enable_crc();      
  lora_set_tx_power(20);   
  
  updateParams(saved_sf);
  printMenu();
}

void loop() {
  handleSerial();

  if (currentMode != IDLE) {
    // 發射模式
    if (millis() - lastSendTime > testInterval) {
      sendPacket();
      lastSendTime = millis(); 

      if ((currentMode == FORMAL_TEST || currentMode == STRESS_TEST) && packetCounter >= packetLimit) {
        Serial.println("\n>>> 測試任務完成，回到待機(接收)模式。");
        currentMode = IDLE;
        lora_idle(); // 切換回 idle/rx
        printMenu();
      }
    }
  } else {
    // 接收模式
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
}

void handleSerial() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    String lowerInput = input;
    lowerInput.toLowerCase(); 
    
    if (lowerInput == "p" || lowerInput.startsWith("p ")) {
      int sf = 7;
      if (lowerInput.startsWith("p ")) {
        if (sscanf(lowerInput.c_str(), "p %d", &sf) != 1 || sf < 6 || sf > 12) {
            sf = 7;
        }
      }
      currentMode = PRE_TEST;
      testInterval = 1000;
      updateParams(sf);
      Serial.print("\n>>> [環境預測量階段] TX SF"); Serial.print(sf); Serial.println(", Interval 1s");
      lastSendTime = millis() - testInterval; 
      
    } else if (lowerInput == "r") {
      Serial.println(">>> RESET STATS");
    } else if (lowerInput == "x") {
      currentMode = IDLE;
      lora_idle();
      Serial.println("\n>>> 已停止發射，回到接收模式。");
      
    } else if (lowerInput.startsWith("u ")) {
      currentUUID = input.substring(2);
      currentUUID.trim();
      Serial.print("\n>>> [設定] UUID 已更改為: ");
      Serial.println(currentUUID);
      
    } else if (lowerInput.startsWith("s ")) {
      int sf = 0, inter = 0;
      if (sscanf(lowerInput.c_str(), "s %d %d", &sf, &inter) == 2) {
        if (sf >= 6 && sf <= 12 && inter > 0) {
          currentMode = STRESS_TEST;
          testInterval = inter;
          updateParams(sf);
          Serial.print("\n>>> [極限壓力測試] TX SF"); Serial.print(sf);
          Serial.print(", Interval "); Serial.print(inter); Serial.println("ms");
          lastSendTime = millis() - testInterval; 
        } else {
          Serial.println(">>> 參數錯誤：SF 需介於 6-12，Interval 需 > 0");
        }
      } else {
        Serial.println(">>> 格式錯誤：請使用 s [SF] [Interval] (例如 s 7 150)");
      }
      
    } else if (lowerInput.startsWith("l ")) {
      int len = 0;
      if (sscanf(lowerInput.c_str(), "l %d", &len) == 1) {
        if (len >= 10 && len <= 255) {
          lora_idle(); // 加入這行，讓底層晶片重新進入 RX 時能套用新的 expected_length (針對 SF6 隱含標頭)
          targetPayloadLength = len;
          prefs.putInt("len", targetPayloadLength);
          Serial.print("\n>>> [設定] 目標封包長度已更改為: "); 
          Serial.print(targetPayloadLength); Serial.println(" Bytes");
        } else {
          Serial.println(">>> 參數錯誤：長度需介於 10 到 255 Bytes 之間");
        }
      } else {
        Serial.println(">>> 格式錯誤：請使用 l [長度] (例如 l 255)");
      }
      
    } else if (lowerInput.startsWith("f ")) {
      long freq = 0;
      if (sscanf(lowerInput.c_str(), "f %ld", &freq) == 1) {
        lora_idle();
        lora_set_frequency(freq);
        prefs.putLong("freq", freq);
        Serial.print("+SET_OK: Freq="); 
        Serial.print(freq / 1E6); Serial.println("MHz");
      }
    } else if (lowerInput.startsWith("b ")) {
      long bw = 0;
      if (sscanf(lowerInput.c_str(), "b %ld", &bw) == 1) {
        lora_idle();
        lora_set_bandwidth(bw);
        prefs.putLong("bw", bw);
        Serial.print("+SET_OK: BW="); 
        Serial.println(bw);
      }
    } else if (lowerInput.startsWith("c ")) {
      int cr = 0;
      if (sscanf(lowerInput.c_str(), "c %d", &cr) == 1) {
        lora_idle();
        lora_set_coding_rate(cr);
        prefs.putInt("cr", cr);
        Serial.print("+SET_OK: CR=4/"); 
        Serial.println(cr);
      }
    } else if (lowerInput.startsWith("v ")) {
      int sf = 0;
      if (sscanf(lowerInput.c_str(), "v %d", &sf) == 1) {
        if (sf >= 6 && sf <= 12) {
          updateParams(sf);
          prefs.putInt("sf", sf);
          Serial.print("+SET_OK: RX_SF="); 
          Serial.println(sf);
        }
      }
    } else {
      int sf = input.toInt();
      if (sf >= 6 && sf <= 12) {
        currentMode = FORMAL_TEST;
        updateParams(sf);
        testInterval = getSafeInterval(sf);
        Serial.print("\n>>> [正式測試階段] TX SF"); Serial.print(sf);
        Serial.print(", Interval "); Serial.print(testInterval); Serial.println("ms");
        lastSendTime = millis() - testInterval; 
      }
    }
  }
}

void updateParams(int sf) {
  currentSF = sf;
  packetCounter = 0;
  lora_idle();
  lora_set_spreading_factor(sf);
}

void sendPacket() {
  unsigned long start = millis();
  
  String payload = "";
  if (currentMode == PRE_TEST) payload += "TST:";
  else if (currentMode == STRESS_TEST) payload += "STR:";
  else payload += "FRM:";
  
  payload += String(packetCounter);
  payload += ":";
  payload += currentUUID;

  while (payload.length() < (size_t)targetPayloadLength) {
    payload += "*"; 
  }

  bool implicit = (currentSF == 6);
  lora_send((const uint8_t*)payload.c_str(), payload.length(), implicit);
  
  unsigned long duration = millis() - start;

  Serial.print(currentMode == PRE_TEST ? "[PRE]" : (currentMode == STRESS_TEST ? "[STRESS]" : "[FORM]"));
  Serial.print(" SF"); Serial.print(currentSF);
  Serial.print(" | ID:"); Serial.print(packetCounter);
  Serial.print(" | UUID:"); Serial.print(currentUUID);
  Serial.print(" | Len:"); Serial.print(payload.length()); 
  Serial.print(" | ToA:"); Serial.print(duration); Serial.println("ms");
  
  packetCounter++;
}

unsigned long getSafeInterval(int sf) {
  if (sf <= 7) return 250;
  if (sf == 8) return 500;
  if (sf == 9) return 1000;
  if (sf == 10) return 2000;
  return 5000; 
}

void printMenu() {
  Serial.println("\n--- 整合控制指令 (TX/RX 通用) ---");
  Serial.println("  f [Hz]     : 設定頻率 (例如 f 915000000)");
  Serial.println("  b [Hz]     : 設定頻寬 (例如 b 125000)");
  Serial.println("  c [CR]     : 設定編碼率分母 (例如 c 6 表示 4/6)");
  Serial.println("  l [Len]    : 設定封包長度 (預設 255 Bytes)");
  Serial.println("  v [SF]     : 設定接收端擴頻因子 (預設 7)");
  Serial.println("  r          : 重置統計數據 (RX)");
  Serial.println("  u [UUID]   : 設定發射端當前測試 UUID");
  Serial.println("  p          : 環境測試(SF7 慢速發送)");
  Serial.println("  6-12       : 正式測試開始(限制發射 100包)");
  Serial.println("  s [SF] [I] : 壓力測試(自定義 SF 與發射頻率)");
  Serial.println("  x          : 停止發射，回到接收模式");
}
