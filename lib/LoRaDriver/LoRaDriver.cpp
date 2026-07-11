#include "LoRaDriver.hpp"
#include "driver/spi_master.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>

#define SCK_PIN   18
#define MISO_PIN  19
#define MOSI_PIN  23
#define NSS_PIN   33
#define RST_PIN   26
#define DIO0_PIN  13

static spi_device_handle_t spi_handle;
static const char* TAG = "LoRaDriver";

static uint8_t read_reg(uint8_t reg) {
    uint8_t tx[2] = {(uint8_t)(reg & 0x7F), 0x00};
    uint8_t rx[2] = {0};
    spi_transaction_t t = {};
    t.length = 16;
    t.tx_buffer = tx;
    t.rx_buffer = rx;
    spi_device_transmit(spi_handle, &t);
    return rx[1];
}

static void write_reg(uint8_t reg, uint8_t val) {
    uint8_t tx[2] = {(uint8_t)(reg | 0x80), val};
    spi_transaction_t t = {};
    t.length = 16;
    t.tx_buffer = tx;
    spi_device_transmit(spi_handle, &t);
}

void lora_init(uint32_t frequency) {
    spi_bus_config_t buscfg = {};
    buscfg.miso_io_num = MISO_PIN;
    buscfg.mosi_io_num = MOSI_PIN;
    buscfg.sclk_io_num = SCK_PIN;
    buscfg.quadwp_io_num = -1;
    buscfg.quadhd_io_num = -1;
    buscfg.max_transfer_sz = 256;

    spi_device_interface_config_t devcfg = {};
    devcfg.clock_speed_hz = 9000000;
    devcfg.mode = 0;
    devcfg.spics_io_num = NSS_PIN;
    devcfg.queue_size = 1;

    // Ignore error if already initialized
    spi_bus_initialize(SPI2_HOST, &buscfg, SPI_DMA_CH_AUTO);
    spi_bus_add_device(SPI2_HOST, &devcfg, &spi_handle);

    gpio_set_direction((gpio_num_t)RST_PIN, GPIO_MODE_OUTPUT);
    gpio_set_level((gpio_num_t)RST_PIN, 0);
    vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_level((gpio_num_t)RST_PIN, 1);
    vTaskDelay(pdMS_TO_TICKS(10));

    // Check version
    uint8_t version = read_reg(0x42);
    if (version != 0x12) {
        ESP_LOGE(TAG, "Unrecognized LoRa version: 0x%02x", version);
    }

    // SLEEP mode
    write_reg(0x01, 0x80); // LoRa mode, SLEEP

    lora_set_frequency(frequency);
    write_reg(0x0F, 0); // RegFifoRxBaseAddr
    write_reg(0x0E, 0); // RegFifoTxBaseAddr

    lora_idle();
    
    // Enable LNA Boost (for HF bands) to improve sensitivity
    uint8_t lna = read_reg(0x0C);
    write_reg(0x0C, lna | 0x03);

    ESP_LOGI(TAG, "LoRa initialized at %lu Hz", frequency);
}

void lora_idle() {
    write_reg(0x01, 0x81); // STANDBY
}

void lora_set_frequency(uint32_t frequency) {
    uint64_t frf = ((uint64_t)frequency << 19) / 32000000;
    write_reg(0x06, (frf >> 16) & 0xFF);
    write_reg(0x07, (frf >> 8) & 0xFF);
    write_reg(0x08, frf & 0xFF);
}

void lora_set_bandwidth(long bw) {
    int bw_val = 9;
    if (bw <= 7800) bw_val = 0;
    else if (bw <= 10400) bw_val = 1;
    else if (bw <= 15600) bw_val = 2;
    else if (bw <= 20800) bw_val = 3;
    else if (bw <= 31250) bw_val = 4;
    else if (bw <= 41700) bw_val = 5;
    else if (bw <= 62500) bw_val = 6;
    else if (bw <= 125000) bw_val = 7;
    else if (bw <= 250000) bw_val = 8;
    else bw_val = 9;

    uint8_t config1 = read_reg(0x1D);
    config1 = (config1 & 0x0F) | (bw_val << 4);
    write_reg(0x1D, config1);
}

void lora_set_coding_rate(int cr) {
    if (cr < 5) cr = 5;
    if (cr > 8) cr = 8;
    int cr_val = cr - 4;
    uint8_t config1 = read_reg(0x1D);
    config1 = (config1 & 0xF1) | (cr_val << 1);
    write_reg(0x1D, config1);
}

void lora_set_spreading_factor(int sf) {
    if (sf < 6) sf = 6;
    if (sf > 12) sf = 12;

    if (sf == 6) {
        uint8_t config1 = read_reg(0x1D);
        write_reg(0x1D, config1 | 0x01); // Implicit header
        write_reg(0x31, 0xC5);
        write_reg(0x37, 0x0C);
    } else {
        uint8_t config1 = read_reg(0x1D);
        write_reg(0x1D, config1 & 0xFE); // Explicit header
        write_reg(0x31, 0xC3);
        write_reg(0x37, 0x0A);
    }

    uint8_t config2 = read_reg(0x1E);
    config2 = (config2 & 0x0F) | (sf << 4);
    write_reg(0x1E, config2);
    
    uint8_t config3 = read_reg(0x26);
    if (sf >= 11) {
        config3 |= 0x08; // LowDataRateOptimize
    } else {
        config3 &= ~0x08;
    }
    config3 |= 0x04; // AgcAutoOn
    write_reg(0x26, config3);
}

void lora_set_preamble_length(long length) {
    write_reg(0x20, (length >> 8) & 0xFF);
    write_reg(0x21, length & 0xFF);
}

void lora_set_sync_word(int sw) {
    write_reg(0x39, sw);
}

void lora_enable_crc() {
    uint8_t config2 = read_reg(0x1E);
    write_reg(0x1E, config2 | 0x04);
}

void lora_set_tx_power(int level) {
    if (level > 17) {
        if (level > 20) level = 20;
        level -= 3;
        write_reg(0x09, 0x80 | (level - 2)); // PA_BOOST
        write_reg(0x4D, 0x87); // PA_DAC high power
    } else {
        if (level < 2) level = 2;
        write_reg(0x09, 0x80 | (level - 2)); // PA_BOOST
        write_reg(0x4D, 0x84); // PA_DAC normal
    }
}

void lora_send(const uint8_t* data, size_t len, bool implicit_header) {
    if (len > 255) len = 255;
    lora_idle();
    write_reg(0x0D, 0); // FIFO PTR = 0
    write_reg(0x0E, 0); // TX BASE = 0
    
    if (implicit_header) {
        write_reg(0x22, len);
    }
    
    for (size_t i = 0; i < len; i++) {
        write_reg(0x00, data[i]);
    }
    
    write_reg(0x22, len); // RegPayloadLength

    write_reg(0x12, 0xFF); // Clear all IRQs before transmitting
    write_reg(0x01, 0x83); // TX mode
    uint32_t start = xTaskGetTickCount();
    while ((read_reg(0x12) & 0x08) == 0) {
        if ((xTaskGetTickCount() - start) > pdMS_TO_TICKS(20000)) break; // 20s timeout
        vTaskDelay(pdMS_TO_TICKS(5));
    }
    write_reg(0x12, 0x08); // Clear IRQ
}

int lora_receive(uint8_t* buf, size_t max_len, int expected_length) {
    uint8_t opMode = read_reg(0x01);
    if (opMode != 0x85) { // If not RXCONTINUOUS
        if (expected_length > 0) {
            write_reg(0x22, expected_length);
        }
        write_reg(0x01, 0x85); // RXCONTINUOUS
        return 0;
    }

    uint8_t irqFlags = read_reg(0x12);
    if ((irqFlags & 0x40) == 0) return 0; // RxDone not set

    write_reg(0x12, irqFlags); // Clear IRQ

    if ((irqFlags & 0x20) != 0) return -1; // PayloadCrcError

    uint8_t len = expected_length > 0 ? expected_length : read_reg(0x13);
    write_reg(0x0D, read_reg(0x10)); // Set FIFO pointer to current RX address

    size_t copy_len = len > max_len ? max_len : len;
    for (size_t i = 0; i < copy_len; i++) {
        buf[i] = read_reg(0x00);
    }
    return copy_len;
}

int lora_packet_rssi() {
    return read_reg(0x1A) - 157; // 157 for HF port (868/915MHz), 164 for LF (433MHz). Typical LoRa.h uses 157.
}

float lora_packet_snr() {
    return ((int8_t)read_reg(0x1B)) * 0.25f;
}
