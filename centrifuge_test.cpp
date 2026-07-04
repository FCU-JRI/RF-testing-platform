#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <FS.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BMP3XX.h>
#include "ICM_20948.h" // SparkFun ICM-20948 library

// =================================================================
// 硬體腳位配置 (TODO: 請依據 Orion v5/v6 實際電路圖修改以下腳位)
// =================================================================
#define I2C_SDA 21
#define I2C_SCL 22
#define SD_CS   5

#define LOG_FILE_NAME "/CENT_LOG.csv"
#define LOG_INTERVAL_MS 20 // 50Hz 採樣率

Adafruit_BMP3XX bmp;
ICM_20948_I2C myICM;

bool isLogging = false;
unsigned long lastLogTime = 0;

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000);
  delay(1000);

  Serial.println(">>> 航電系統洗衣機離心力測試韌體啟動");

  // 初始化 I2C
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);

  // 初始化 SD 卡
  if (!SD.begin(SD_CS)) {
    Serial.println(">>> [ERROR] SD 卡初始化失敗！請檢查接腳或 SD 卡是否插入");
    while (1);
  }
  Serial.println(">>> [OK] SD 卡初始化成功");

  // 初始化感測器 (BMP388)
  if (!bmp.begin_I2C()) {
    Serial.println(">>> [ERROR] BMP388 找不到！");
  } else {
    bmp.setTemperatureOversampling(BMP3_OVERSAMPLING_8X);
    bmp.setPressureOversampling(BMP3_OVERSAMPLING_4X);
    bmp.setIIRFilterCoeff(BMP3_IIR_FILTER_COEFF_3);
    bmp.setOutputDataRate(BMP3_ODR_50_HZ);
    Serial.println(">>> [OK] BMP388 初始化成功");
  }

  // 初始化感測器 (ICM20948)
  bool initialized = false;
  while (!initialized) {
    myICM.begin(Wire, 1); // 預設 I2C 地址通常為 0x69 (1) 或 0x68 (0)
    if (myICM.status != ICM_20948_Stat_Ok) {
      Serial.println(">>> [ERROR] ICM20948 找不到！重試中...");
      delay(500);
    } else {
      initialized = true;
      Serial.println(">>> [OK] ICM20948 初始化成功");
    }
  }

  // 寫入 CSV 標頭
  if (!SD.exists(LOG_FILE_NAME)) {
    File file = SD.open(LOG_FILE_NAME, FILE_WRITE);
    if (file) {
      file.println("Timestamp_ms,AccX_g,AccY_g,AccZ_g,GyroX_dps,GyroY_dps,GyroZ_dps,Pressure_Pa,Temp_C");
      file.close();
    }
  }

  Serial.println(">>> [系統狀態] 開機即自動開始背景紀錄數據...");
  Serial.println(">>> [USB 指令] 輸入 DUMP 可下載數據，輸入 CLEAR 可清空 SD 卡");
  isLogging = true;
}

void loop() {
  // 處理來自 Python Manager 的 USB 指令
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    if (cmd == "DUMP") {
      isLogging = false; // 下載期間暫停紀錄
      Serial.println(">>> 準備匯出資料...");
      File file = SD.open(LOG_FILE_NAME, FILE_READ);
      if (!file) {
        Serial.println("NO_DATA");
      } else {
        while (file.available()) {
          Serial.write(file.read());
        }
        file.close();
        Serial.println("EOF");
      }
      isLogging = true;
    } 
    else if (cmd == "CLEAR") {
      isLogging = false;
      if (SD.exists(LOG_FILE_NAME)) {
        SD.remove(LOG_FILE_NAME);
      }
      // 重新建立標頭
      File file = SD.open(LOG_FILE_NAME, FILE_WRITE);
      if (file) {
        file.println("Timestamp_ms,AccX_g,AccY_g,AccZ_g,GyroX_dps,GyroY_dps,GyroZ_dps,Pressure_Pa,Temp_C");
        file.close();
      }
      Serial.println("CLEARED");
      isLogging = true;
    }
  }

  // 執行 50Hz 高頻紀錄
  if (isLogging && (millis() - lastLogTime >= LOG_INTERVAL_MS)) {
    lastLogTime = millis();
    
    if (myICM.dataReady()) {
      myICM.getAGMT();
    }
    bmp.performReading();

    File file = SD.open(LOG_FILE_NAME, FILE_APPEND);
    if (file) {
      // Timestamp, Acc(X,Y,Z), Gyro(X,Y,Z), Pressure, Temp
      file.print(millis()); file.print(",");
      file.print(myICM.accX() / 1000.0, 3); file.print(","); // 轉成 g
      file.print(myICM.accY() / 1000.0, 3); file.print(",");
      file.print(myICM.accZ() / 1000.0, 3); file.print(",");
      file.print(myICM.gyrX(), 2); file.print(",");
      file.print(myICM.gyrY(), 2); file.print(",");
      file.print(myICM.gyrZ(), 2); file.print(",");
      file.print(bmp.pressure); file.print(",");
      file.print(bmp.temperature);
      file.println();
      
      file.close(); // 每次關閉確保寫入 (避免震動斷電遺失)，若追求更高頻率可改為每 10 筆 flush()
    }
  }
}
