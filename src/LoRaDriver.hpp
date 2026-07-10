#pragma once
#include <stdint.h>
#include <stddef.h>

void lora_init(uint32_t frequency);
void lora_send(const uint8_t* data, size_t len, bool implicit_header);

void lora_idle();
void lora_set_frequency(uint32_t frequency);
void lora_set_bandwidth(long bw);
void lora_set_coding_rate(int cr);
void lora_set_spreading_factor(int sf);
void lora_set_preamble_length(long length);
void lora_set_sync_word(int sw);
void lora_enable_crc();
void lora_set_tx_power(int level);

// Returns length of received packet, 0 if no packet, < 0 if CRC error
int lora_receive(uint8_t* buf, size_t max_len, int expected_length);
int lora_packet_rssi();
float lora_packet_snr();
